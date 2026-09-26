import argparse
import asyncio
import faulthandler
import json
import os
import signal
import time

from kafka_server_sdk import KafkaBasedServer, AsyncKafkaServer, ServerConfig
from kafka_server_sdk.kafka_server.exceptions.need_repeat import NeedRepeatException
from logic.kafka_service import echo_payload


def trace(kind, request):
    entry = {'kind': kind, 'entry': request.headers['entry_id'], 'key': request.key,
             'sequence': int(request.headers['sequence']), 'node': os.environ['PARALLEL_LAB_NODE'],
             'pid': os.getpid(), 'time': time.monotonic(), 'attempt': request.headers.get('__repeat_count', '0')}
    fd = os.open(os.environ['PARALLEL_LAB_TRACE'], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(entry) + '\n').encode())
    finally:
        os.close(fd)


def start(request):
    trace('start', request)
    if request.headers.get('fail_once') == '1' and request.headers.get('__repeat_count', '0') == '0':
        trace('retry', request)
        raise NeedRepeatException('intentional one-shot acceptance-test retry')


def result_headers(request):
    return dict(request.headers, lab_node=os.environ['PARALLEL_LAB_NODE'], lab_pid=str(os.getpid()))


def sync_factory(context):
    def handle(request):
        start(request)
        time.sleep(float(request.headers.get('delay', '.04')))
        context.send_response(request, request.key, result_headers(request), echo_payload(request.value))
        trace('end', request)
    return {'in': handle}


def async_factory(context):
    async def handle(request):
        start(request)
        await asyncio.sleep(float(request.headers.get('delay', '.04')))
        await context.asend_response(request, request.key, result_headers(request), echo_payload(request.value))
        trace('end', request)
    return {'in': handle}


class SyncLogic(KafkaBasedServer):
    def init_handlers(self):
        self.set_handler('in', sync_factory(self)['in'])


class AsyncLogic(AsyncKafkaServer):
    def init_handlers(self):
        self.set_handler('in', async_factory(self)['in'])


def main():
    faulthandler.register(signal.SIGUSR1)
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('--mode', choices=['sync', 'async'], default='sync')
    args = parser.parse_args()
    server = (AsyncLogic if args.mode == 'async' else SyncLogic)(ServerConfig.load_from_file(args.config))
    server.run_forever()


if __name__ == '__main__':
    main()
