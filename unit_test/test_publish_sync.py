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



class AgentResponse(Agent):
    def on_connected(self):
        self._subscribe('topic_1')
    
    
    def on_message(self, topic:str, data):
        logger.debug(self.M(f"topic: {topic}, data: {data}"))
        time.sleep(1)
        self._publish('topic_2', int(data)+1)



class TestAgent(unittest.TestCase):
    data_resp = 0
    data_resp_a = 0
    data_got = False
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=config_test)


        def on_connected(self):
            time.sleep(1)
            # self._publish('topic_1', 1)
            TestAgent.data_resp = int(self._publish_sync('topic_1', 1, 'topic_2'))
            TestAgent.data_resp_a = int(self._publish_sync('topic_1', TestAgent.data_resp, 'topic_2'))
            TestAgent.data_got = True


    def setUp(self):
        self.agent_resp = AgentResponse('aaa', config_test)
        self.agent_resp.start()

        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        self.assertTrue(TestAgent.data_got)
        self.assertEqual(TestAgent.data_resp, 2)
        self.assertEqual(TestAgent.data_resp_a, 3)


    def test_1(self):
        time.sleep(4)

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.validation_agent.terminate()
        self.agent_resp.terminate()



if __name__ == '__main__':
    unittest.main()
