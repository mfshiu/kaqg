import hashlib
import os
import random
import time
import uuid

from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel

from logging import Logger
logger:Logger = __import__('src').get_logger()


class FileService(Agent):
    def __init__(self, cfg, storage_root):
        super().__init__('file_service.services.wastepro', cfg)
        self.storage_root = storage_root


    def on_connected(self):
        self._subscribe("FileUpload/FileService/Services", "str", self.handle_file_upload)
                
        
    def _generate_file_id(filename):        
        current_time = str(int(time.time() * 1000)) # Get the current time in milliseconds since the epoch
        combined_input = filename + current_time + str(random.randint(0, 999)).zfill(3)
        sha1_hash = hashlib.sha1(combined_input.encode()).hexdigest()
        generated_uuid = str(uuid.UUID(sha1_hash[:32])).replace('-', '')
        
        return generated_uuid


    def handle_file_upload(self, topic:str, data):
        parcel = Parcel.from_bytes(data)
        logger.debug(f"topic: {topic}, filename: {parcel.get('filename')}, content size: {len(parcel.content)}")

        filename = parcel.get('filename')
        file_id = FileService._generate_file_id(filename)
        
        file_dir = os.path.join(self.storage_root, file_id[:2])
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)
        file_path = os.path.join(file_dir, f"{file_id}-{filename}")
        open_mode = "w" if isinstance(parcel.content, str) else "wb"
        with open(file_path, open_mode) as fp:
            fp.write(parcel.content)
        logger.info(f"topic: {topic}, File saved.")

        if parcel.home_topic:
            resp = {
                'file_id': file_id,
                'filename': filename,
            }
            self._publish(parcel.home_topic, resp)
