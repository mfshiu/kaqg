# Main program required
import os, sys

from knowsys import docker_management
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import app_helper
app_helper.initialize()

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel, TextParcel
from retrieval.pdf_retriever import PdfRetriever
from services.file_service import FileService
from services.kg_service import KnowledgeGraphService, Topic as KGTopic
from knowsys.docker_management import DockerManager



class TestAgent(unittest.TestCase):
    kg_name = 'S01'
    # test_files = ['Pdf01-台文.pdf', 'Pdf01-English.pdf', 'Pdf01-日本語.pdf']
    test_files = ['1.廢棄物管理概論(甲乙丙級).pdf']
    # test_files = ['Pdf01-台文.pdf']
    file_ids = []
    filenames = []
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=app_helper.get_agent_config())
            self.kg_name = TestAgent.kg_name
            kg_config = app_helper.config['service']['kg']
            logger.info(f"kg_config: {kg_config}")
            self.docker_management = DockerManager(kg_config['hostname'], kg_config['datapath'])


        def on_activate(self):
            logger.info("on_connected")

            self.subscribe(PdfRetriever.TOPIC_RETRIEVED)
            
            self.publish_sync(KGTopic.CREATE, TextParcel({'kg_name': self.kg_name}), timeout=20)
            
            for filename in TestAgent.test_files:
                with open(os.path.join(os.getcwd(), 'unit_test', 'data', filename), 'rb') as file:
                    content = file.read()
                pcl = BinaryParcel({
                    'content': content,
                    'filename': filename,
                    'kg_name': self.kg_name})
                self.publish(PdfRetriever.TOPIC_FILE_UPLOAD, pcl)


        def on_message(self, topic:str, pcl:Parcel):
            logger.debug(self.M(f"topic: {topic}, len(data): {len(pcl.content)}"))

            TestAgent.file_ids.append(pcl['file_id'])
            TestAgent.filenames.append(pcl['filename'])
            
            
        def on_terminated(self):
            pass
            # self.docker_management.stop_KG(self.kg_name)


    def setUp(self):
        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        logger.debug(f'file_ids: {TestAgent.file_ids}')
        
        self.assertEqual(len(TestAgent.file_ids), len(TestAgent.test_files))
        for testfile in TestAgent.test_files:
            self.assertTrue(testfile in TestAgent.filenames)


    def test_1(self):
        # time.sleep(5)
        
        for _ in range(100):
            time.sleep(1)
            if len(TestAgent.file_ids) == len(TestAgent.test_files):
                break
            print('.', end='')

        self._do_test_1()


    def tearDown(self):
        self.validation_agent.terminate()
        
        if hasattr(self, 'kgservice'):
            self.kgservice.terminate()
        if hasattr(self, 'knowledge_retriever'):
            self.knowledge_retriever.terminate()
        if hasattr(self, 'file_agent'):
            self.file_agent.terminate()



if __name__ == '__main__':
    unittest.main()
