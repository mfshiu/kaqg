import sys
import os
sys.path.append(os.path.abspath(".."))  # Adjust path if necessary

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel
from generation.scq_generator import SingleChoiceGenerator
from unit_test.config_test import config_test


from logging import Logger
logger:Logger = __import__('wastepro').get_logger()



class AgentResponse(Agent):
    def on_connected(self):
        self._subscribe('topic_1')
    
    
    def on_message(self, topic:str, pcl:Parcel):
        data = pcl.content
        logger.debug(self.M(f"topic: {topic}, data: {data}"))
        time.sleep(1)
        return int(data) + 1



class TestAgent(unittest.TestCase):
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=config_test)
            self.generated_question = None


        def on_connected(self):
            time.sleep(1)   # Waiting for other agents to start.
            
            topic_return = f'{self.agent_id}/SCQ_TEST'
            self._subscribe(topic_return)

            question_criteria = {
                'question_id': 'Q101',              # 使用者自訂題目 ID
                'section': ['chapter1', 'ch1-1'],   # 指定章節
                'difficulty': 50,                   # 難度 30, 50, 70
            }
            pcl = Parcel.from_content(question_criteria)
            pcl.topic_return = topic_return
            self._publish(SingleChoiceGenerator.TOPIC_CREATE, pcl)
            
            
        def on_message(self, topic: str, pcl:Parcel):
            logger.info(f'topic: {topic}, contgent: {pcl.content}')
            self.generated_question = pcl.content



    def setUp(self):
        self.agent_scq = SingleChoiceGenerator(config_test)
        self.agent_scq.start()

        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def _do_test_1(self):
        generated_question = self.validation_agent.generated_question
        self.assertTrue(generated_question['type'], 'SCQ')


    def test_1(self):
        time.sleep(3)

        try:
            self._do_test_1()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.agent_scq.terminate()
        self.validation_agent.terminate()



if __name__ == '__main__':
    unittest.main()
