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
#from services.kg_service import KnowledgeGraphService, Action, Topic
from services.kg_service import Topic

config_test = app_helper.get_agent_config()
logger.info(f"config_test: {config_test}")



class TestAgent(unittest.TestCase):
    kg_name = None
    http_url = None
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='validation', agent_config=config_test)


        def on_connected(self):
            time.sleep(1)

            return_topic = self.agent_id
            self.subscribe(return_topic)
            
            pcl = TextParcel({'kg_name': 'kg01'}, return_topic)
            self.publish(Topic.CREATE, pcl)


        def on_message(self, topic:str, pcl:Parcel):
            kg_info:dict = pcl.content
            logger.debug(self.M(f"topic: {topic}, kg_info: {kg_info}"))

            TestAgent.kg_name = kg_info.get('kg_name')
            TestAgent.http_url = kg_info.get('http_url')


    def setUp(self):
        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        logger.debug(f'kg_name: {TestAgent.kg_name}')
        self.assertEqual('kg01', TestAgent.kg_name)
        self.assertTrue(TestAgent.http_url)


    def test_1(self):
        # 等待 CREATE 回覆（建立容器 + Neo4j 就緒可能超過 30 秒，最多等 180 秒）
        timeout = 180
        step = 2
        for _ in range(0, timeout, step):
            if TestAgent.kg_name is not None:
                break
            time.sleep(step)

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.validation_agent.terminate()



if __name__ == '__main__':
    unittest.main()
