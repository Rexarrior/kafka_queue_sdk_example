import json
from pathlib import Path

import kafka_queue_client
import kafka_server_sdk
import pytest

from kafka_server_sdk.kafka_server.server_config import ServerConfig
from kafka_server_sdk.queue_admin import QueueAdminConfig
from kafka_server_sdk.service_admin import AdminApiConfig
from kafka_server_sdk.service_templates.common.auth import AuthConfig
from kafka_server_sdk.service_templates.hold_service.app_config import HoldServiceConfig
from kafka_server_sdk.service_templates.in_gateway.app_config import InGatewayConfig
from kafka_server_sdk.service_templates.message_storage.app_config import MessageStorageConfig
from kafka_server_sdk.service_templates.out_gateway.app_config import OutGatewayConfig


ROOT = Path(__file__).resolve().parents[1]
AUTH_ENV = "KAFKA_QUEUE_AUTH_PASSWORD"

HTTP_CONFIGS = [
    ROOT / "admin/config.json",
    ROOT / "file_storage/config.json",
    ROOT / "file_storage/local_config.json",
    ROOT / "hold_service/config.json",
    ROOT / "hold_service_2/config.json",
    ROOT / "in_gateway/config.json",
    ROOT / "out_gateway/config.json",
]
ADMIN_CONFIGS = [
    ROOT / "file_storage/admin_config.json",
    ROOT / "hold_service/admin_config.json",
    ROOT / "hold_service_2/admin_config.json",
    ROOT / "logic/admin_config.json",
    ROOT / "out_gateway/admin_config.json",
]
SERVER_CONFIGS = list(ROOT.glob("*/server_config.json"))
REQUIREMENTS = list(ROOT.glob("*/requirements.txt"))


@pytest.fixture(autouse=True)
def auth_password(monkeypatch):
    monkeypatch.setenv(AUTH_ENV, "migration-test-password")
    monkeypatch.setenv("POSTGRES_PASSWORD", "migration-test-postgres")
    monkeypatch.setenv("SCALITY_ACCESS_KEY_ID", "migration-test-access")
    monkeypatch.setenv("SCALITY_SECRET_ACCESS_KEY", "migration-test-secret")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_sdk_and_client_are_on_the_same_major_release():
    assert kafka_server_sdk.__version__ == "1.0.0"
    assert kafka_queue_client.__version__ == "1.0.0"


@pytest.mark.parametrize("path", HTTP_CONFIGS + ADMIN_CONFIGS)
def test_auth_is_explicit_and_uses_no_plaintext_password(path):
    auth = load_json(path)["auth"]
    assert auth["enabled"] is True
    assert auth["credentials"]
    assert all("password" not in credential for credential in auth["credentials"])
    assert all(
        credential.get("password_env") == AUTH_ENV
        or credential.get("password_hash")
        for credential in auth["credentials"]
    )
    AuthConfig(auth)


def test_all_application_configs_load_with_sdk_1():
    InGatewayConfig.load_from_file(ROOT / "in_gateway/config.json")
    OutGatewayConfig.load_from_file(ROOT / "out_gateway/config.json")
    MessageStorageConfig.load_from_file(ROOT / "file_storage/config.json")
    MessageStorageConfig.load_from_file(ROOT / "file_storage/local_config.json")
    HoldServiceConfig(ROOT / "hold_service/config.json")
    HoldServiceConfig(ROOT / "hold_service_2/config.json")
    QueueAdminConfig.load_from_file(ROOT / "admin/config.json")


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "in_gateway/config.json",
        ROOT / "out_gateway/config.json",
        ROOT / "file_storage/config.json",
        ROOT / "file_storage/local_config.json",
    ],
)
def test_postgres_password_is_injected(path):
    pg_config = load_json(path)["pg_config"]
    assert "password" not in pg_config
    assert pg_config["password_env"] == "POSTGRES_PASSWORD"


def test_s3_credentials_are_injected():
    storage = load_json(ROOT / "file_storage/config.json")["storage"]
    assert "access_key" not in storage
    assert "sec_key" not in storage
    assert storage["access_key_env"] == "SCALITY_ACCESS_KEY_ID"
    assert storage["sec_key_env"] == "SCALITY_SECRET_ACCESS_KEY"


def test_local_environment_file_is_ignored_and_has_a_safe_template():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert ".env" in ignored
    assert "KAFKA_QUEUE_AUTH_PASSWORD=replace-with-a-long-random-value" in example
    assert "POSTGRES_PASSWORD=replace-me" in example
    assert "SCALITY_SECRET_ACCESS_KEY=replace-me" in example


def test_compose_initializes_the_required_s3_bucket():
    compose = (ROOT / "docker-compose.yaml").read_text(encoding="utf-8")
    assert "s3-init:" in compose
    assert "mc mb --ignore-existing local/files" in compose
    assert "condition: service_completed_successfully" in compose


@pytest.mark.parametrize("path", ADMIN_CONFIGS)
def test_observer_directories_are_confined_and_capture_is_opt_in(path):
    config = load_json(path)
    assert config["capture_payload"] is False
    assert config["capture_headers"] is False
    AdminApiConfig.load_from_file(path)


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "in_gateway/config.json",
        ROOT / "file_storage/config.json",
        ROOT / "file_storage/local_config.json",
    ],
)
def test_upload_limit_is_explicit(path):
    assert load_json(path)["max_upload_bytes"] == 100 * 1024 * 1024


@pytest.mark.parametrize("path", SERVER_CONFIGS)
def test_kafka_consumer_config_uses_framework_managed_offsets(path):
    config = load_json(path)
    consumer = config.get("default.consumer", {})
    assert "enable.auto.commit" not in consumer
    assert "enable.auto.offset.store" not in consumer
    ServerConfig.load_from_file(path)


def test_queue_admin_has_explicit_downstream_credentials():
    services = load_json(ROOT / "admin/config.json")["services"]
    for service in services.values():
        assert service["auth"] == {
            "username": "admin",
            "password_env": AUTH_ENV,
        }


@pytest.mark.parametrize("path", REQUIREMENTS)
def test_every_image_pins_both_sdk_distributions(path):
    requirements = path.read_text(encoding="utf-8").splitlines()
    assert "kafka_server_sdk==1.0.0" in requirements
    assert "kafka_queue_client==1.0.0" in requirements
