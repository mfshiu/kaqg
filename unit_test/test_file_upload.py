import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel
import app_helper, log_helper
from services.file_service import FileService

from logging import Logger
logger:Logger = __import__('agentflow').get_logger()


config_test = app_helper.get_agent_config()



class TestAgent(unittest.TestCase):
    file_id = None
    filename = None
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=config_test)


        def on_connected(self):
            self._subscribe('file_uploaded')
            
            time.sleep(1)
            filename = 'test_img1.jpg'
            with open(os.path.join(os.getcwd(), 'unit_test', 'data', filename), 'rb') as file:
                content = file.read()
            # pcl = BinaryParcel(content, 'file_uploaded')
            # pcl.set('filename', filename)
            pcl = BinaryParcel({
                'content': content,
                'filename': filename}, 'file_uploaded')
            self._publish('FileUpload/FileService/Services', pcl)


        def on_message(self, topic:str, pcl:Parcel):
            file_info:dict = pcl.content
            logger.debug(self.M(f"topic: {topic}, file_info: {file_info}"))

            TestAgent.file_id = file_info.get('file_id')
            TestAgent.filename = file_info.get('filename')


    def setUp(self):
        storage_root = os.path.join(os.getcwd(), '_upload')
        if not os.path.exists(storage_root):
            os.mkdir(storage_root)
        self.file_agent = FileService(config_test, storage_root)
        self.file_agent.start()

        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        logger.debug(f'file_id: {TestAgent.file_id}')
        self.assertTrue(TestAgent.file_id)
        self.assertEqual('test_img1.jpg', TestAgent.filename)


    def test_1(self):
        time.sleep(3)

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.validation_agent.terminate()
        if hasattr(self, 'file_agent'):
            self.file_agent.terminate()



if __name__ == '__main__':
    logger = log_helper.get_logger()

    unittest.main()
