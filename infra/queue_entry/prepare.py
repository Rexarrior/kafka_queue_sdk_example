"""Generate the opt-in Compose configs; files contain env names, not passwords."""
import argparse
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]


def prepare(destination, *, local_files=False):
    destination.mkdir(parents=True, exist_ok=True)
    for service in ("in_gateway", "out_gateway", "file_storage", "admin"):
        cfg = json.loads((root / service / "config.json").read_text())
        if service == "file_storage" and local_files:
            cfg.update(storage_type="local", storage={"root_path": "/var/lib/queue-files"})
        if service == "admin":
            cfg["client_api"] = {"enabled": True, "max_request_bytes": 104857600}
        else:
            cfg["auth"]["credentials"].append({
                "username": "queue-client", "password_env": "KAFKA_QUEUE_CLIENT_PASSWORD"
            })
        (destination / f"{service}.json").write_text(json.dumps(cfg, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=root / ".queue-entry")
    parser.add_argument("--local-files", action="store_true", help="Use with compose.queue-local-files.yaml in a fresh test stack only.")
    args = parser.parse_args()
    prepare(args.output, local_files=args.local_files)
