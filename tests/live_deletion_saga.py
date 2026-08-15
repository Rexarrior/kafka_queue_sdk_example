"""Live smoke test for PostgreSQL-to-storage deletion reconciliation."""

import json
import os
import time

from kafka_queue_client import TaskQueueClient


def run():
    password = os.environ.get("KAFKA_QUEUE_AUTH_PASSWORD")
    external_id = os.environ.get("KAFKA_QUEUE_TEST_EXTERNAL_ID")
    if not password or not external_id:
        raise RuntimeError(
            "KAFKA_QUEUE_AUTH_PASSWORD and KAFKA_QUEUE_TEST_EXTERNAL_ID must be set"
        )

    with TaskQueueClient(
        user="admin",
        password=password,
        incoming_url=os.environ.get("KAFKA_QUEUE_IN_URL", "http://localhost:7091"),
        progress_url=os.environ.get("KAFKA_QUEUE_OUT_URL", "http://localhost:7092"),
        files_url=os.environ.get("KAFKA_QUEUE_FILES_URL", "http://localhost:7093"),
    ) as client:
        before, status = client.files.list_files_by_ext_id(external_id)
        assert status == 200
        messages = before["stored_messages"]
        assert messages, "The completed session has no stored files"
        entry_id = sorted(message["session_entry_id"] for message in messages)[0]

        _, delete_status = client.files.delete_file_by_entry(entry_id)
        assert delete_status in (202, 204)

        deadline = time.monotonic() + 30
        remaining = None
        while time.monotonic() < deadline:
            current, current_status = client.files.list_files_by_ext_id(external_id)
            assert current_status == 200
            remaining = current["stored_messages"]
            if all(message["session_entry_id"] != entry_id for message in remaining):
                break
            time.sleep(0.25)
        else:
            raise TimeoutError("Deletion reconciliation did not remove file metadata")

    print(
        json.dumps(
            {
                "delete_status": delete_status,
                "deleted_entry_id": entry_id,
                "files_before": len(messages),
                "files_after": len(remaining),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run()
