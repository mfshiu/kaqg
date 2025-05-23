# Main program required
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import app_helper
app_helper.initialize()

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel, Parcel
from services.kg_service import KnowledgeGraphService, Action, Topic

config_test = app_helper.get_agent_config()
logger.info(f"config_test: {config_test}")



class TestAgent(unittest.TestCase):
    file_id = None
    filename = None
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='validation', agent_config=config_test)


        def on_connected(self):
            time.sleep(1)

            return_topic = self.agent_id
            self.subscribe(return_topic)
            
            pcl = TextParcel({
                'content': content,
                'filename': filename,
                'hello': 'how are you?'
            }, return_topic)
            self.publish(Topic.CREATE, pcl)


        def on_message(self, topic:str, pcl:Parcel):
            file_info:dict = pcl.content
            logger.debug(self.M(f"topic: {topic}, file_info: {file_info}"))

            TestAgent.file_id = file_info.get('file_id')
            TestAgent.filename = file_info.get('filename')


    def setUp(self):
        # Comment here if FileService is started at another location.
        # self.file_agent = FileService(config_test, storage_root)
        # self.file_agent.start()

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
    unittest.main()
