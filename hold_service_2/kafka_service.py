import os
from flask_restx.apidoc import apidoc
# apidoc.static_url_path = "/out/swaggerui"
from kafka_server_sdk.service_templates.hold_service.run import run
from kafka_server_sdk.common import Logger

log_dir = os.path.join(os.path.dirname(__file__), "logs")
Logger().init_logging(log_dir, "DEBUG", 5, 10)
api_config_path = "./config.json"
admin_config_path = "./admin_config.json"
server_config_path = "./server_config.json"
run(api_config_path, server_config_path, admin_config_path)
