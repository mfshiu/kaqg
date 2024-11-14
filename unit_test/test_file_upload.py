import sys
import os
sys.path.append(os.path.abspath(".."))  # Adjust path if necessary

import random
import threading
import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.config import EventHandler
from agentflow.core.parcel import Parcel
from services.file_service import FileService
from unit_test.config_test import config_test


from logging import Logger
logger:Logger = __import__('wastepro').get_logger()



class TestAgent(unittest.TestCase):
    file_id = None
    filename = None
    
    class ValidationAgent(Agent):
        def __init__(self):
            config_test['storage_root'] = r'D:\Work\NCU\計畫\國環院廢棄物\wastepro\_upload'
            super().__init__(name='main', agent_config=config_test)


        def on_connected(self):
            self._subscribe('file_uploaded')
            
            with open(r'unit_test\test_img.jpg', 'rb') as file:
                content = file.read()
            pcl = Parcel(content, 'file_uploaded')
            pcl.set('filename', 'test_img.jpg')
            self._publish('FileUpload/FileService/Services', pcl.payload())


        def on_message(self, topic:str, data):
            logger.debug(self.M(f"topic: {topic}, len(data): {len(data)}"))
            
            p = Parcel.from_text(data)
            TestAgent.file_id = p.get('file_id')
            TestAgent.filename = p.get('filename')


    def setUp(self):
        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()
        
        self.file_agent = FileService(config_test)
        self.file_agent.start()


    def _do_test_1(self):
        logger.debug(f'file_id: {TestAgent.file_id}')
        self.assertTrue(TestAgent.file_id)
        self.assertEqual('test_img.jpg', TestAgent.filename)


    def test_1(self):
        time.sleep(3)

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.file_agent.terminate()
        self.validation_agent.terminate()



if __name__ == '__main__':
    unittest.main()
