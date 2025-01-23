# Main program required
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize()

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

import hashlib
import mimetypes
import random
import uuid

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel



class FileService(Agent):
    TOPIC_FILE_UPLOAD = "FileUpload/FileService/Services"
    
    
    def __init__(self, agent_config, home_directory):
        logger.info(f"FileService.__init__")
        super().__init__('file_service.services.wastepro', agent_config)
        self.home_directory = home_directory


    def on_connected(self):
        logger.info(f"subscribe: {FileService.TOPIC_FILE_UPLOAD}")
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
        # print(f"topic: {topic}, filename: {file_info.get('filename')}, content size: {len(file_info.get('content'))}")

        filename = file_info.get('filename')
        file_id = FileService._generate_file_id(filename)
        mime_type, encoding = mimetypes.guess_type(filename)
        logger.debug(f"file_id: {file_id}, filename: {filename}, mime_type: {mime_type}, encoding: {encoding}")
        
        file_dir = os.path.join(self.home_directory, file_id[:2])
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



import signal
import time
from datetime import datetime

if __name__ == '__main__':
    _agent = FileService(
        agent_config = app_helper.get_agent_config(), 
        home_directory = app_helper.config['service']['file']['home_directory'])
    logger.info(f'***** {_agent.__class__.__name__} *****')
    
    def signal_handler(signal, frame):
        _agent.terminate()
    signal.signal(signal.SIGINT, signal_handler)

    _agent.start_process()

    time.sleep(1)
    dot_counter = 0
    minute_tracker = datetime.now().minute

    while _agent.is_active():
        time.sleep(1)
        
        dot_counter += 1
        if dot_counter % 6 == 0:
            print('.', end='', flush=True)

        current_minute = datetime.now().minute
        if current_minute != minute_tracker:
            print(f"\n{datetime.now().strftime('%H:%M')}")
            minute_tracker = current_minute
            
    # time.sleep(1)
    # while _agent.is_active():
    #     print('.', end='', flush=True)
    #     time.sleep(1)
