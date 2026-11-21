"""Same SDK scenario at either origin. Only hold release uses operator credentials."""
import asyncio
import json
from hashlib import shake_256
from collections import Counter
from io import BytesIO
import os
from uuid import uuid4
from zipfile import ZipFile

import httpx
from kafka_queue_client import AsyncTaskQueueClient, TaskQueueClient
from live_client_cycle import wait_and_unhold


def expected_bytes(n, i):
    # Deterministic binary data. Even a single multipart is >1 MiB.
    return shake_256(f"queue-entry:{n}:{i}".encode()).digest(64 * 1024)


def archive(n):
    f = BytesIO()
    with ZipFile(f, "w") as z:
        for i in range(17):
            z.writestr(f"{i}.jpg", expected_bytes(n, i))
    f.seek(0)
    return f


async def test_mode(asynchronous, count):
    url = os.environ["KAFKA_QUEUE_URL"].rstrip("/")
    uid = uuid4().hex
    auth = ("queue-client", os.environ["KAFKA_QUEUE_CLIENT_PASSWORD"])
    for path, permitted in [("/out/list_sessions", (401, 403)),
                            ("/admin/queue_info", (401, 403, 404))]:
        r = httpx.get(url + path, auth=auth if path.startswith("/admin") else None)
        assert r.status_code in permitted, (path, r.status_code)
    sdk = (AsyncTaskQueueClient if asynchronous else TaskQueueClient)(url, *auth)

    async def call(fn, *args, **kwargs):
        return (await fn(*args, **kwargs)) if asynchronous else fn(*args, **kwargs)

    try:
        headers = [{"metadata": {"smoke": uid, "input": n}} for n in range(count)]
        submitted = await call(sdk.send_new_task, [archive(n) for n in range(count)], headers, uid)
        ids = {x.entry_id for x in submitted.tasks_info}
        assert len(ids) == count * 17 and submitted.external_id == uid
        await asyncio.to_thread(wait_and_unhold, ids, os.environ["KAFKA_QUEUE_AUTH_PASSWORD"])
        task = await call(sdk.wait_for_ready, submitted, timeout=180, interval=0.25)
        assert (task.session_uid, task.external_id, task.status) == (submitted.session_uid, uid, "completed")
        assert {x.entry_id for x in task.entries_info} == ids
        found = Counter()
        for entry in task.entries_info:
            assert (entry.session_uid, entry.status, entry.step) == (submitted.session_uid, "completed", "file_storage")
            payload, status = await call(sdk.files.get_file_by_entry, entry.entry_id)
            assert status == 200
            with ZipFile(BytesIO(payload)) as z:
                member, = z.namelist()
                meta = json.loads(entry.metadata_json)
                assert meta["smoke"] == uid
                n, i = meta["input"], int(member.removesuffix(".jpg"))
                assert z.read(member) == expected_bytes(n, i)
                found[n, i] += 1
        assert found == Counter((n, i) for n in range(count) for i in range(17))
    finally:
        if asynchronous:
            await sdk.aclose()
        else:
            sdk.close()
    print(f"{url}: {'async' if asynchronous else 'sync'} {count} input(s), {len(ids)} verified results", flush=True)


async def main():
    for asynchronous in (False, True):
        for count in (1, 2):
            await test_mode(asynchronous, count)


if __name__ == "__main__":
    asyncio.run(main())
