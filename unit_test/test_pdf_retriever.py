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
    file_ids = []
    filenames = []
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=app_helper.get_agent_config())
            self.kg_name = 'TestKG'
            kg_config = app_helper.config['service']['kg']
            logger.info(f"kg_config: {kg_config}")
            self.docker_management = DockerManager(kg_config['hostname'], kg_config['datapath'])


        def on_activate(self):
            logger.info("on_connected")

            self.subscribe(PdfRetriever.TOPIC_RETRIEVED)
            
            self.publish_sync(KGTopic.CREATE, TextParcel({'kg_name': self.kg_name}), timeout=20)
            # self.docker_management.create_container(self.kg_name)
            
            for filename in ['Pdf01-台文.pdf', 'Pdf01-English.pdf', 'Pdf01-日本語.pdf']:
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
            self.docker_management.stop_KG(self.kg_name)


    def setUp(self):
        # Comment here if related agents is started.
        # storage_root = os.path.join(os.getcwd(), '_upload')
        # if not os.path.exists(storage_root):
        #     os.mkdir(storage_root)
        # self.file_agent = FileService(config_test, storage_root)
        # self.file_agent.start()
        
        # self.kgservice = KnowledgeGraphService(config_test)
        # self.kgservice.start()
        
        # self.knowledge_retriever = PdfRetriever(config_test)
        # self.knowledge_retriever.start()

        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        logger.debug(f'file_ids: {TestAgent.file_ids}')
        self.assertEqual(len(TestAgent.file_ids), 3)
        self.assertTrue('Pdf01-台文.pdf' in TestAgent.filenames)
        self.assertTrue('Pdf01-English.pdf' in TestAgent.filenames)
        self.assertTrue('Pdf01-日本語.pdf' in TestAgent.filenames)


    def test_1(self):
        # time.sleep(5)
        
        for _ in range(100):
            time.sleep(1)
            if len(TestAgent.file_ids) == 3:
                break
            print('.', end='')

        self._do_test_1()
        # try:
        #     self._do_test_1()
        # except Exception as ex:
        #     logger.exception(ex)
        #     self.assertTrue(False)


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
