import os
from kafka_server_sdk import KafkaBasedServer, ServerConfig
from kafka_server_sdk.common import Logger
from kafka_server_sdk.service_admin import AdminApiConfig
import kafka_server_sdk.service_admin as debug_api

log_dir = os.path.join(os.path.dirname(__file__), "logs")
Logger().init_logging(log_dir, "DEBUG", 5, 10)

server_config_path = "./server_config.json"
admin_config_path = "./admin_config.json"


class LogicServer(KafkaBasedServer):
    def init_handlers(self):
        """
        Initializes the handlers for the class instance.
        """
        self.set_handler("in", self.process_logic)

    def process_logic(self, request):
        """
        Process the logic request and send the response (echo/mirror).
        """
        Logger().log_info(f"Processing request: {request.key}")
        
        # Simply return the same data (echo/mirror)
        self.send_response(
            request,
            request.key,
            request.headers,
            request.value
        )


if __name__ == "__main__":
    cfg = ServerConfig.load_from_file(server_config_path)
    admin_config = AdminApiConfig.load_from_file(admin_config_path)
    
    server = LogicServer(cfg)
    
    # Start debug/admin API in a separate thread
    debug_api.start_api(server, admin_config)
    
    # Run the main server
    server.run()
