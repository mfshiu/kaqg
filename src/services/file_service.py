import hashlib
import mimetypes
import os
import random
import time
import uuid

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel

from logging import Logger
logger:Logger = __import__('src').get_logger()


class FileService(Agent):
    TOPIC_FILE_UPLOAD = "FileUpload/FileService/Services"
    
    
    def __init__(self, cfg, storage_root):
        super().__init__('file_service.services.wastepro', cfg)
        self.storage_root = storage_root


    def on_connected(self):
        self._subscribe(FileService.TOPIC_FILE_UPLOAD, "str", self.handle_file_upload)


    def _generate_file_id(filename):        
        current_time = str(int(time.time() * 1000))
        combined_input = filename + current_time + str(random.randint(0, 999)).zfill(3)
        sha1_hash = hashlib.sha1(combined_input.encode()).hexdigest()
        generated_uuid = str(uuid.UUID(sha1_hash[:32])).replace('-', '')
        
        return generated_uuid


    def handle_file_upload(self, topic:str, pcl:BinaryParcel):
        file_info = pcl.content
        logger.verbose(f"topic: {topic}, filename: {file_info.get('filename')}, content size: {len(file_info.get('content'))}")

        filename = file_info.get('filename')
        file_id = FileService._generate_file_id(filename)
        mime_type, encoding = mimetypes.guess_type(filename)
        
        file_dir = os.path.join(self.storage_root, file_id[:2])
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)

        file_path = os.path.join(file_dir, f"{file_id}-{filename}")
        content = file_info.get('content')
        open_mode = "w" if isinstance(content, str) else "wb"
        with open(file_path, open_mode) as fp:
            fp.write(content)
        logger.info(f"filename: {filename} is saved.")

        return {
            'file_id': file_id,
            'filename': filename,
            'mime_type': mime_type,
            'encoding': encoding,
            'file_path': file_path,
        }
