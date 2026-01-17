import os
from kafka_server_sdk.queue_admin import start, QueueAdminConfig

from kafka_server_sdk import Logger


if __name__ == "__main__":
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    Logger().init_logging(log_dir, "DEBUG", 5, 10)
    curr_dir = os.path.dirname(__file__)
    admin_config_path = os.path.join(curr_dir, "config.json")
    config = QueueAdminConfig.load_from_file(admin_config_path)
    start(config)