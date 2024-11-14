import sys
import os
sys.path.append(os.path.abspath(".."))  # Adjust path if necessary

import random
import threading
import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.config import EventHandler
from agentflow.core.parcel import Parcel
from 
from unit_test.config_test import config_test


from logging import Logger
logger:Logger = __import__('AgentFlow').get_logger()



class TestAgent(unittest.TestCase):
    file_id = None
    filename = None
    
    class ValidationAgent(Agent):
        def __init__(self):
            config_test['storage_root'] = r'D:\Work\SDK\AgentFlow\_upload'
            super().__init__(name='main', agent_config=config_test)


        def on_connected(self):
            self._subscribe('file_uploaded')


        def on_message(self, topic:str, data):
            logger.debug(self.M(f"topic: {topic}, len(data): {len(data)}"))
            
            p = Parcel.from_text(data)
            TestAgent.file_id = p.get('file_id')
            TestAgent.filename = p.get('filename')


    def setUp(self):
        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()
        
        def send_binary():
            def do_send():
                time.sleep(random.uniform(0.5, 1.5))
                self.binary_agent._publish('binary_payload', Parcel(bytes([72, 101, 108, 108, 111])).payload())
            threading.Thread(target=do_send).start()
        
        cfg = config_test.copy()
        cfg[EventHandler.ON_CONNECTED] = send_binary
        self.file_agent = File(name='main.binary', agent_config=cfg)
        self.binary_agent.start()


    def _do_test_binary(self):
        logger.info(f'TestAgent.binary_data: {TestAgent.binary_data}')
        content = TestAgent.binary_data['content']
        self.assertTrue(isinstance(content, bytes))
        self.assertEqual(content, bytes([72, 101, 108, 108, 111]))


    def _do_test_text(self):
        logger.info(f'TestAgent.text_data: {TestAgent.text_data}')
        content = TestAgent.text_data['content']
        self.assertTrue(isinstance(content, str))
        self.assertEqual(content, '早安, Anita.')


    def test_1(self):
        time.sleep(3)

        try:
            self._do_test_binary()
            self._do_test_text()
        except Exception as ex:
            logger.exception(ex)
            self.assertTrue(False)


    def tearDown(self):
        self.validation_agent.terminate()



if __name__ == '__main__':
    unittest.main()
