import os
from tempfile import TemporaryDirectory
from flask_restx.apidoc import apidoc
apidoc.static_url_path = "/in/swaggerui"
from kafka_server_sdk.service_templates.common.exceptions import BadInputDataExcception
from kafka_server_sdk.service_templates.in_gateway import run
from kafka_server_sdk.common import Logger
import kafka_server_sdk
from typing import Dict


IMG_FORMAT = "jpg"

def transform_calback(headers: Dict, file_content: bytes, ext_uid: str):
    all_headers = []
    all_contents = []
    all_uids = []
    with TemporaryDirectory() as tmp_dir:
        filename = os.path.join(tmp_dir, "archive")
        kafka_server_sdk.tools.write_bytes(file_content, filename)
        kafka_server_sdk.tools.extract_zip_file(filename, tmp_dir)
        for i in range(0, 17):
            basename =  f"{i}.{IMG_FORMAT}"
            fname = os.path.join(tmp_dir, basename) 
            if not os.path.exists(fname):
                Logger().log_debug(f"File {basename} not found! Files in {tmp_dir}: {os.listdir(tmp_dir)}")
                raise BadInputDataExcception(f"File {basename} not found in input archive")

            zip_file_basename = f"{i}.zip"
            zip_fname = os.path.join(tmp_dir, zip_file_basename)
            kafka_server_sdk.tools.zip_files([fname], tmp_dir, zip_fname)
            content = kafka_server_sdk.tools.read_bytes(zip_fname)
            curr_headers = headers.copy()
            curr_headers["step"] = str(i)
            all_headers.append(curr_headers)
            all_contents.append(content)
            all_uids.append(ext_uid)

        return all_headers, all_contents, all_uids
        


log_dir = os.path.join(os.path.dirname(__file__), "logs")
Logger().init_logging(log_dir, "DEBUG", 5, 10)
config_path = "./config.json"
run(config_path, transform_calback)