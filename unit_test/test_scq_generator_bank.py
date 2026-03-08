# BankQuestionGenerator 整合測試
# 需先啟動 llm_service 與 MQTT broker。（BankQuestionGenerator 不需 kg_service）
#
# 用法（專案根目錄）：
#   1. 啟動 llm_service：python -m services.llm_service
#   2. 執行測試：python -m unit_test.test_scq_generator_bank

import os
import sys
import time
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

import logging
logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel

from generation.scq_generator_bank import BankQuestionGenerator


class TestBankQuestionGenerator(unittest.TestCase):

    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='test_bank_gen', agent_config=app_helper.get_agent_config())
            self.generated_question = None

        def on_activate(self):
            time.sleep(2)  # 等待 BankQuestionGenerator 與 llm_service 就緒

            topic_return = f'{self.agent_id}/BANK_SCQ_TEST'
            self.subscribe(topic_return)

            question_criteria = {
                'subject': 'H67013',   # 題庫科目代碼（_data/generation/H67013.xlsx）
                '章': None,             # 可指定章，None 則科目內隨機
            }
            pcl = Parcel.from_content(question_criteria)
            pcl.topic_return = topic_return
            self.publish(BankQuestionGenerator.TOPIC_CREATE, pcl)

        def on_message(self, topic: str, pcl: Parcel):
            logger.info('topic: %s, content keys: %s', topic, list(pcl.content.keys()) if isinstance(pcl.content, dict) else type(pcl.content))
            self.generated_question = pcl.content

    def setUp(self):
        self.agent_bank = BankQuestionGenerator(app_helper.get_agent_config())
        self.agent_bank.start_thread()

        self.validation_agent = self.ValidationAgent()
        self.validation_agent.start_thread()

    def _do_test_generate(self):
        generated = self.validation_agent.generated_question
        logger.info('generated_question: %s', generated)
        self.assertIsNotNone(generated)
        self.assertIn('question_criteria', generated)
        self.assertIn('question', generated)
        q = generated['question']
        self.assertIn('stem', q)
        self.assertTrue((q.get('stem') or '').strip(), '題幹不應為空')
        self.assertFalse((q.get('stem') or '').startswith('【系統錯誤】'), '不應為系統錯誤題')

    def test_generate(self):
        time.sleep(60)  # LLM 首次呼叫可能較慢
        try:
            self._do_test_generate()
        except Exception as ex:
            logger.exception(ex)
            self.fail(str(ex))

    def tearDown(self):
        self.validation_agent.terminate()
        self.agent_bank.terminate()


if __name__ == '__main__':
    unittest.main()
