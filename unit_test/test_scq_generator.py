# Required when executed as the main program.
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###
import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel
from generation.scq_generator import SingleChoiceGenerator
from config_test import config_test

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))



class AgentResponse(Agent):
    def on_connected(self):
        self.subscribe('topic_1')
    
    
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


        def on_activate(self):
            time.sleep(1)   # Waiting for other agents to start.
            
            topic_return = f'{self.agent_id}/SCQ_TEST'
            self.subscribe(topic_return)

            question_criteria = {
                'question_id': 'Q101',              # 使用者自訂題目 ID
                'subject':  'W0301',                # 科目編碼
                'document': 'Wastepro02',           # 教材名稱
                # 'section': ['貳、廢棄物清理專業技術人員相關法規及其職掌', '一、廢棄物清理專業技術人員所涉相關法規'],   # 指定章節
                'section': ['貳、廢棄物清理專業技術人員相關法規及其職掌'],   # 指定章節
                'difficulty': 50,                   # 難度 30, 50, 70
            }
            pcl = Parcel.from_content(question_criteria)
            pcl.topic_return = topic_return
            self.publish(SingleChoiceGenerator.TOPIC_CREATE, pcl)
            
            
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
        time.sleep(20)

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
