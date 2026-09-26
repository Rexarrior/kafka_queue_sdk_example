"""Real Kafka acceptance runner. Never reads .env or modifies existing topics/DBs."""
import argparse
from collections import Counter
import io
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
from zipfile import ZipFile

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

ROOT = Path(__file__).resolve().parents[1]


def wait_until(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise TimeoutError('Acceptance condition did not become true')


def trace_rows(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # Writer may still be appending the final line.
    return rows


def run_case(case, bootstrap, output, sdk_root):
    name = case['name']
    folder = output / name
    folder.mkdir(parents=True, exist_ok=False)
    trace = folder / 'trace.jsonl'
    prefix = 'parallel-lab-' + name.replace('_', '-') + '-' + uuid4().hex[:10]
    in_topic, out_topic, event_topic = [prefix + s for s in ('-in', '-out', '-events')]
    group = prefix + '-workers'
    admin = AdminClient({'bootstrap.servers': bootstrap})
    for future in admin.create_topics([NewTopic(in_topic, case['partitions'], 1),
                                      NewTopic(out_topic, 1, 1), NewTopic(event_topic, 1, 1)]).values():
        future.result(20)
    producer = Producer({'bootstrap.servers': bootstrap})
    reader = Consumer({'bootstrap.servers': bootstrap, 'group.id': prefix + '-reader', 'enable.auto.commit': False})
    verifier = Consumer({'bootstrap.servers': bootstrap, 'group.id': group, 'enable.auto.commit': False})
    reader.assign([TopicPartition(out_topic, 0, 0)])
    nodes, log_files = [], []
    assignments = []
    cfg_base = json.loads((ROOT / 'logic/server_config.json').read_text())
    count = 96 if case.get('rebalance') else 40
    delay = '.15' if case.get('rebalance') or case.get('crash') else '.04'

    def launch(index):
        node = f'{name}-node-{index}'
        cfg = dict(cfg_base)
        cfg.update({'default': {'bootstrap.servers': bootstrap},
            'default.consumer': {'group.id': group, 'client.id': node,
                'auto.offset.reset': 'earliest', 'session.timeout.ms': 6000,
                'heartbeat.interval.ms': 1000, 'max.poll.interval.ms': 60000,
                'partition.assignment.strategy': case.get('strategy', 'range')},
            'default.producer': {'delivery.timeout.ms': 10000},
            'topics': {'in': {'topic': in_topic, 'poll_timeout': .02},
                       'out': {'topic': out_topic}, 'events': {'topic': event_topic}},
            'server_id': node, 'processing': dict({'max_inflight': 32,
                'shutdown_timeout_seconds': 5}, **case['processing']),
            'broken_repeat_mode': 'on_need_repeat_error', 'max_repeat_count': 1})
        config = folder / f'{node}.json'
        config.write_text(json.dumps(cfg, indent=2))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(sdk_root), str(sdk_root / 'client')]),
                   PARALLEL_LAB_TRACE=str(trace), PARALLEL_LAB_NODE=node)
        log = (folder / f'{node}-{len(nodes)}.log').open('w')
        log_files.append(log)
        process = subprocess.Popen([sys.executable, '-m', 'parallel_lab.service', str(config), '--mode', case['mode']],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        nodes.append(process)
        return process

    def ready(expected):
        def check():
            try:
                description = admin.describe_consumer_groups([group])[group].result(5)
                owners = {}
                for member in description.members:
                    partitions = [tp.partition for tp in member.assignment.topic_partitions if tp.topic == in_topic]
                    if partitions:
                        owners.setdefault(member.client_id, []).extend(partitions)
                if description.state.name == 'STABLE' and len(owners) == expected and sum(map(len, owners.values())) == case['partitions']:
                    assignments.append(owners)
                    return True
            except Exception:
                pass
            return False
        wait_until(check)

    expected, received = {}, []
    committed = []
    stop_codes = []
    try:
        first = launch(0)
        if not case.get('rebalance'):
            for i in range(1, case['replicas']):
                launch(i)
        ready(1 if case.get('rebalance') else case['replicas'])
        for i in range(count):
            archive = io.BytesIO()
            with ZipFile(archive, 'w') as zipped:
                zipped.writestr(f'{i}.jpg', f'example-payload-{i}'.encode())
            entry = f'{prefix}-entry-{i}'
            headers = {'entry_id': entry, 'session_uid': prefix + f'-session-{i % 5}', 'client': f'parallel-lab-{i % 3}',
                       'sequence': str(i), 'delay': delay, 'metadata': json.dumps({'index': i})}
            if case.get('retry') and i % 7 == 0:
                headers['fail_once'] = '1'
            expected[entry] = {'payload': archive.getvalue(), 'headers': headers, 'key': f'lane-{i % 4}'}
            producer.produce(in_topic, partition=i % case['partitions'], key=expected[entry]['key'],
                             value=archive.getvalue(), headers=headers)
        assert producer.flush(10) == 0
        if case.get('rebalance') or case.get('crash'):
            wait_until(lambda: bool(trace_rows(trace)))
            if case.get('rebalance'):
                launch(1)
                ready(2)
            else:
                first.kill()
                first.wait(5)
                launch(0)
                ready(1)
        targets = [sum(i % case['partitions'] == p for i in range(count)) for p in range(case['partitions'])]
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            msg = reader.poll(.05)
            if msg is not None and not msg.error():
                headers = {k: v.decode() for k, v in msg.headers()}
                original = expected[headers['entry_id']]
                assert msg.value() == original['payload'], 'payload corruption or cross-message mix'
                assert msg.key().decode() == original['key']
                for key, value in original['headers'].items():
                    assert headers[key] == value, f'header mismatch: {key}'
                received.append(headers)
            if len({r['entry_id'] for r in received}) == count:
                committed = verifier.committed([TopicPartition(in_topic, p) for p in range(case['partitions'])], timeout=5)
                if [p.offset for p in committed] == targets:
                    break
        assert len({r['entry_id'] for r in received}) == count, f'missing outputs: {count - len({r["entry_id"] for r in received})}'
        assert [p.offset for p in committed] == targets, 'commit frontier did not reach end'
        # Collect already queued duplicates after the final commit.
        deadline = time.monotonic() + .3
        while time.monotonic() < deadline:
            msg = reader.poll(.05)
            if msg is not None and not msg.error():
                received.append({k: v.decode() for k, v in msg.headers()})
        duplicates = len(received) - count
        if not case.get('rebalance') and not case.get('crash'):
            assert duplicates == 0, f'unexpected duplicate outputs: {duplicates}'
        rows = trace_rows(trace)
        if case.get('retry'):
            assert sum(r['kind'] == 'retry' for r in rows) == len(range(0, count, 7)), 'retry was not exercised'
        if case['processing'].get('processes', 1) > 1:
            assert len({r['lab_pid'] for r in received}) == case['processing']['processes'], 'not all process workers ran'
        active, peak = 0, 0
        lane_active = Counter()
        for row in rows:
            if row['kind'] == 'start':
                active += 1
                peak = max(peak, active)
                if case['processing']['ordering'] == 'key':
                    assert lane_active[row['key']] == 0, 'same key overlapped'
                    lane_active[row['key']] += 1
            else:
                active -= 1
                if case['processing']['ordering'] == 'key':
                    lane_active[row['key']] -= 1
        if not case.get('rebalance') and not case.get('crash'):
            expected_peak = case['processing']['concurrency'] * case['processing'].get('processes', 1) * case['replicas']
            if case['processing']['ordering'] == 'partition':
                expected_peak = min(expected_peak, case['partitions'])
            assert 1 <= peak <= expected_peak, f'concurrency exceeded: {peak} > {expected_peak}'
            if expected_peak > 1:
                assert peak > 1, 'processing remained serial'
            assert active == 0, 'unfinished handler traces'
        output_nodes = sorted({r['lab_node'] for r in received})
        if case['replicas'] > 1:
            assert len(output_nodes) == case['replicas'], 'Kafka failed to distribute work across nodes'
        if case['processing']['ordering'] in ('key', 'partition') and not case.get('rebalance'):
            for key in {r['key'] for r in rows}:
                sequence = [r['sequence'] for r in rows if r['kind'] == 'end' and r['key'] == key]
                assert sequence == sorted(sequence), 'ordering violation'
        duration = max(r['time'] for r in rows) - min(r['time'] for r in rows)
        result = {'scenario': name, 'status': 'passed', 'messages': count, 'outputs': len(received),
                  'duplicates': duplicates, 'peak_observed': peak, 'handling_seconds': round(duration, 3),
                  'messages_per_second': round(count / duration, 2), 'nodes': output_nodes,
                  'worker_pids': sorted({r['lab_pid'] for r in received}), 'assignments': assignments,
                  'committed_offsets': [p.offset for p in committed], 'topics': [in_topic, out_topic, event_topic]}
        return result
    finally:
        for node in nodes:
            if node.poll() is None:
                node.terminate()
        for node in nodes:
            try:
                node.wait(10)
            except subprocess.TimeoutExpired:
                node.send_signal(signal.SIGUSR1)
                time.sleep(.2)
                node.kill()
                node.wait(5)
            stop_codes.append(node.returncode)
        for log in log_files:
            log.close()
        reader.close()
        verifier.close()
        producer.flush(3)
        (folder / 'exit_codes.json').write_text(json.dumps(stop_codes))
        expected_codes = [-signal.SIGKILL, 0] if case.get('crash') else [0] * len(nodes)
        assert stop_codes == expected_codes, f'unclean shutdown: {stop_codes}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bootstrap', default='127.0.0.1:29092')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sdk-root', type=Path, default=ROOT.parent / 'kafkaQueueSdk')
    parser.add_argument('--scenario', action='append')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = json.loads((ROOT / 'parallel_lab/scenarios.json').read_text())
    results = []
    for case in cases:
        if args.scenario and case['name'] not in args.scenario:
            continue
        try:
            result = run_case(case, args.bootstrap, args.output.resolve(), args.sdk_root)
        except Exception as exc:
            result = {'scenario': case['name'], 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
        results.append(result)
        print(json.dumps(result), flush=True)
        (args.output / 'results.json').write_text(json.dumps(results, indent=2))
    if not results or any(r['status'] != 'passed' for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
