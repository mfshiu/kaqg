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
from services.llm_service import Topic

config_test = app_helper.get_agent_config()
logger.info(f"config_test: {config_test}")



class TestAgent(unittest.TestCase):
    llm_result:dict = {}
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='validation', agent_config=config_test)


        def on_connected(self):
            time.sleep(1)

            return_topic = self.agent_id
            self.subscribe(return_topic)
            
            messages = [
                {"role": "user", "content": 'How are you?'},
                # {"role": "user", "content": f"{message}\nPlease provide your response in JSON format."}
            ]            
            params = {
                'messages': messages,
            }            
            pcl = TextParcel(params, return_topic)
            self.publish(Topic.LLM_PROMPT, pcl)


        def on_message(self, topic:str, pcl:Parcel):
            TestAgent.llm_result = pcl.content
            logger.debug(self.M(f"topic: {topic}, llm_result: {TestAgent.llm_result}"))


    def setUp(self):
        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        self.assertTrue(TestAgent.llm_result['response'])


    def test_1(self):
        time.sleep(10)  # wait for async response

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.validation_agent.terminate()



if __name__ == '__main__':
    unittest.main()
