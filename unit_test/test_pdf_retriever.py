import sys
import os
sys.path.append(os.path.abspath(".."))  # Adjust path if necessary

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel
from retrieval.pdf_retriever import PdfRetriever
from services.file_service import FileService
from services.kg_service import KnowledgeGraphService
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
            self._subscribe(PdfRetriever.TOPIC_RETRIEVED)
            
            for filename in ['test_img1.jpg', 'test_img2.jpg', 'test_img3.jpg']:
                time.sleep(.5)
                with open(os.path.join(os.getcwd(), 'unit_test', 'data', filename), 'rb') as file:
                    content = file.read()
                pcl = BinaryParcel({
                    'content': content,
                    'filename': filename})
                self._publish(PdfRetriever.TOPIC_FILE_UPLOAD, pcl)


        def on_message(self, topic:str, pcl:Parcel):
            logger.debug(self.M(f"topic: {topic}, len(data): {len(pcl.content)}"))

            TestAgent.file_ids.append(pcl['file_id'])
            TestAgent.filenames.append(pcl['filename'])


    def setUp(self):
        storage_root = os.path.join(os.getcwd(), '_upload')
        if not os.path.exists(storage_root):
            os.mkdir(storage_root)
        self.file_agent = FileService(config_test, storage_root)
        self.file_agent.start()
        
        self.kgservice = KnowledgeGraphService(config_test)
        self.kgservice.start()
        
        self.knowledge_retriever = PdfRetriever(config_test)
        self.knowledge_retriever.start()

        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        logger.debug(f'file_ids: {TestAgent.file_ids}')
        self.assertEqual(len(TestAgent.file_ids), 3)
        self.assertTrue('test_img1.jpg' in TestAgent.filenames)
        self.assertTrue('test_img2.jpg' in TestAgent.filenames)
        self.assertTrue('test_img3.jpg' in TestAgent.filenames)


    def test_1(self):
        # time.sleep(5)
        
        for _ in range(10):
            time.sleep(1)
            if len(TestAgent.file_ids) == 3:
                break
            print('.', end='')

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.validation_agent.terminate()
        self.kgservice.terminate()
        self.knowledge_retriever.terminate()
        self.file_agent.terminate()



if __name__ == '__main__':
    unittest.main()
