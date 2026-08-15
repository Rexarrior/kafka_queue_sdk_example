"""Live end-to-end smoke test for the public kafka_queue_client facade.

The Compose stack must already be running. Authentication is read only from
KAFKA_QUEUE_AUTH_PASSWORD; this script never loads or prints .env.
"""

import io
import json
import os
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import httpx

from kafka_queue_client import TaskQueueClient, __version__


EXPECTED_FILES = 17
AUTH_USER = "admin"
INCOMING_URL = os.environ.get("KAFKA_QUEUE_IN_URL", "http://localhost:7091")
PROGRESS_URL = os.environ.get("KAFKA_QUEUE_OUT_URL", "http://localhost:7092")
FILES_URL = os.environ.get("KAFKA_QUEUE_FILES_URL", "http://localhost:7093")
HOLD_URL = os.environ.get(
    "KAFKA_QUEUE_HOLD_URL",
    "http://localhost:7097/hold_admin_panel",
)


def require_iso_timestamp(value, field):
    assert value, f"{field} is empty"
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def wait_for_client_health(client, timeout=90):
    deadline = time.monotonic() + timeout
    checks = (client.incoming, client.progress, client.files)
    while time.monotonic() < deadline:
        try:
            if all(service.healthcheck()[0] for service in checks):
                return
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    raise TimeoutError("Queue HTTP services did not become healthy")


def build_input_archive(directory):
    archive_path = Path(directory) / "client-live-input.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for index in range(EXPECTED_FILES):
            archive.writestr(f"{index}.jpg", f"client-live-payload-{index}".encode())
    return archive_path


def wait_and_unhold(entry_ids, password, timeout=90):
    auth = (AUTH_USER, password)
    deadline = time.monotonic() + timeout
    with httpx.Client(auth=auth, timeout=10) as hold_client:
        while time.monotonic() < deadline:
            response = hold_client.get(f"{HOLD_URL}/held_messages")
            response.raise_for_status()
            held = {
                str(message["message_key"]): message
                for message in response.json()["messages"]
            }
            if entry_ids <= held.keys():
                for entry_id in sorted(entry_ids):
                    release = hold_client.post(
                        f"{HOLD_URL}/held_messages/{held[entry_id]['id']}/unhold"
                    )
                    release.raise_for_status()
                    assert release.json()["status"] == "success"
                return
            time.sleep(0.5)
    raise TimeoutError("Submitted entries did not reach the primary hold service")


def assert_zip(payload, expected_member_count=None):
    stream = io.BytesIO(payload)
    assert zipfile.is_zipfile(stream), "Downloaded payload is not a ZIP archive"
    with zipfile.ZipFile(stream) as archive:
        names = archive.namelist()
        if expected_member_count is not None:
            assert len(names) == expected_member_count
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in names)
        assert all(archive.read(name) for name in names if not name.endswith("/"))


def run():
    password = os.environ.get("KAFKA_QUEUE_AUTH_PASSWORD")
    if not password:
        raise RuntimeError("KAFKA_QUEUE_AUTH_PASSWORD must be set")
    assert __version__ == "1.0.0", f"Unexpected client version: {__version__}"

    external_id = f"client-live-{uuid.uuid4()}"
    metadata = {"smoke": "public-client", "external_id": external_id}

    with TaskQueueClient(
        user=AUTH_USER,
        password=password,
        incoming_url=INCOMING_URL,
        progress_url=PROGRESS_URL,
        files_url=FILES_URL,
    ) as client:
        wait_for_client_health(client)
        with tempfile.TemporaryDirectory(prefix="kafka-client-live-") as temp_dir:
            archive_path = build_input_archive(temp_dir)
            submitted = client.send_new_task(
                str(archive_path),
                {"metadata": metadata},
                external_uid=external_id,
            )

        assert submitted.external_id == external_id
        assert submitted.session_uid and submitted.session_uid != "not_unique"
        assert len(submitted.tasks_info) == EXPECTED_FILES
        assert all(task.status == "Success" for task in submitted.tasks_info)
        assert all(task.session_uid == submitted.session_uid for task in submitted.tasks_info)
        entry_ids = {task.entry_id for task in submitted.tasks_info}
        assert "" not in entry_ids
        assert len(entry_ids) == EXPECTED_FILES

        wait_and_unhold(entry_ids, password)
        completed = client.wait_for_ready(
            submitted,
            timeout=180,
            interval=0.5,
            retries=20,
        )

        assert completed.external_id == external_id
        assert completed.session_uid == submitted.session_uid
        assert completed.status == "completed"
        require_iso_timestamp(completed.created_at, "session.created_at")
        require_iso_timestamp(completed.updated_at, "session.updated_at")
        assert len(completed.entries_info) == EXPECTED_FILES
        assert {entry.entry_id for entry in completed.entries_info} == entry_ids
        for entry in completed.entries_info:
            assert entry.session_uid == completed.session_uid
            assert entry.status == "completed"
            assert entry.step == "file_storage"
            assert entry.enabled is True
            assert entry.validated is False
            assert json.loads(entry.metadata_json) == metadata
            require_iso_timestamp(entry.created_at, f"entry[{entry.entry_id}].created_at")
            require_iso_timestamp(entry.updated_at, f"entry[{entry.entry_id}].updated_at")

        files_response, files_status = client.files.list_files_by_ext_id(external_id)
        assert files_status == 200
        stored_messages = files_response["stored_messages"]
        assert len(stored_messages) == EXPECTED_FILES
        assert {message["session_entry_id"] for message in stored_messages} == entry_ids
        for message in stored_messages:
            assert message["session_uid"] == completed.session_uid
            assert message["address"]
            require_iso_timestamp(message["created_at"], "stored_message.created_at")
            require_iso_timestamp(message["updated_at"], "stored_message.updated_at")
            headers = json.loads(message["headers"])
            assert headers["entry_id"] == message["session_entry_id"]
            assert headers["session_uid"] == completed.session_uid

        combined = client.get_file_for_task(completed)
        assert_zip(combined, EXPECTED_FILES)
        for entry_id in entry_ids:
            single, status = client.files.get_file_by_entry(entry_id)
            assert status == 200
            assert_zip(single, 1)

    print(json.dumps({
        "client_version": __version__,
        "external_id": external_id,
        "session_uid": completed.session_uid,
        "submitted_entries": len(entry_ids),
        "completed_entries": len(completed.entries_info),
        "stored_files": len(stored_messages),
        "downloaded_files": len(entry_ids),
        "session_status": completed.status,
        "terminal_step": "file_storage",
    }, sort_keys=True))


if __name__ == "__main__":
    run()
