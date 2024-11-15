import sys
import os
sys.path.append(os.path.abspath(".."))  # Adjust path if necessary

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel
from retrieval.knowledge_retriever import KnowledgeRetriever
from services.file_service import FileService
from unit_test.config_test import config_test


from logging import Logger
logger:Logger = __import__('wastepro').get_logger()



class TestAgent(unittest.TestCase):
    file_ids = []
    filenames = []
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=config_test)


        def on_connected(self):
            self._subscribe('001/Test')
            
            for filename in ['test_img1.jpg', 'test_img2.jpg', 'test_img3.jpg']:
                with open(os.path.join(os.getcwd(), 'unit_test', 'data', filename), 'rb') as file:
                    content = file.read()
                pcl = Parcel(content, 'file_uploaded')
                pcl.set('filename', filename)
                self._publish('FileUpload/Retrieval', pcl.payload())


        def on_message(self, topic:str, data):
            logger.debug(self.M(f"topic: {topic}, len(data): {len(data)}"))

            p = Parcel.from_text(data)
            TestAgent.file_ids.append(p.get('file_id'))
            TestAgent.filenames.append(p.get('filename'))


    def setUp(self):
        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()
        
        storage_root = os.path.join(os.getcwd(), '_upload')
        if not os.path.exists(storage_root):
            os.mkdir(storage_root)
        self.file_agent = FileService(config_test, storage_root)
        self.file_agent.start()
        
        self.knowledge_retriever = KnowledgeRetriever(config_test)
        self.knowledge_retriever.start()


    def _do_test_1(self):
        logger.debug(f'file_ids: {TestAgent.file_ids}')
        self.assertEqual(len(TestAgent.file_ids), 3)
        self.assertTrue('test_img1.jpg' in TestAgent.filenames)
        self.assertTrue('test_img2.jpg' in TestAgent.filenames)
        self.assertTrue('test_img3.jpg' in TestAgent.filenames)


    def test_1(self):
        time.sleep(3)

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.knowledge_retriever.terminate()
        self.file_agent.terminate()
        self.validation_agent.terminate()



if __name__ == '__main__':
    unittest.main()
