# Required when executed as the main program.
from logging import config
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from enum import Enum, StrEnum, auto
import time

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel
from services.llms.base_llm import BaseLLM
from services.llms.chat_llm import ChatLLM
from services.llms.ossgpt_llm import OssGptLLM



class Topic(StrEnum):
    LLM_PROMPT = 'Prompt/LlmService/Services'



class LlmModel(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    ChatGpt = auto()
    Claude = auto()
    LLama = auto()
    OssGpt = auto()



class LlmService(Agent):
    SERVICE_NAME = 'llm_service.services.kaqg'
    TOPIC_LLM_PROMPT = Topic.LLM_PROMPT.value

    _default_llm_params = {
        'name': LlmModel.ChatGpt,
    }
    
    
    def __init__(self, agent_config):
        logger.debug(f"{LlmService.__name__}.{self.__init__.__name__}")
        super().__init__(LlmService.SERVICE_NAME, agent_config)
        self.llm_params = agent_config.get('llm')
        logger.debug(f"self.llm_params: {self.llm_params}")


    @staticmethod
    def _generate_llm_model(llm_params=None):
        params:dict = LlmService._default_llm_params.copy()
        if llm_params:
            params.update(llm_params)

        llm_name = params['name']
        llm_config = params[llm_name]
        logger.debug(f"llm_name: {llm_name}, llm_config: {llm_config}")
        if llm_name == LlmModel.ChatGpt.value:
            llm = ChatLLM(llm_config)
        elif llm_name == LlmModel.Claude.value:
            llm = ChatLLM(llm_config)
        elif llm_name == LlmModel.LLama.value:
            llm = ChatLLM(llm_config)
        elif llm_name == LlmModel.OssGpt.value:
            llm = OssGptLLM(llm_config)
        else:
            llm = ChatLLM(llm_config)
        
        return llm
    

    def on_activate(self):
        self.llm:BaseLLM = LlmService._generate_llm_model(self.llm_params)
        
        self.subscribe(LlmService.TOPIC_LLM_PROMPT, "str", self.handle_prompt)


    def handle_prompt(self, topic:str, pcl:TextParcel):
        params = pcl.content
        logger.verbose(f"params: {params}")

        response = self.llm.generate_response(params['messages'])
        logger.debug(self.M(response))

        return {
            'response': response,
        }



if __name__ == '__main__':
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='validation', agent_config=app_helper.get_agent_config())


        def on_connected(self):
            time.sleep(2)

            self.subscribe(self.agent_id)
            
            pcl = TextParcel({
                'messages': "現在的美國總統是誰？",
                }, topic_return=self.agent_id)
            logger.info(self.M(f"pcl: {pcl}"))
            self.publish(LlmService.TOPIC_LLM_PROMPT, pcl)


        def on_message(self, topic:str, pcl:TextParcel):
            logger.info(self.M(f"topic: {topic}"))
            logger.info(f"pcl:\n{pcl}")

            self.terminate()
            # llm_agent.terminate()


    if "-test" in sys.argv:
        ValidationAgent().start_thread()
    else:
        config = app_helper.get_agent_config()
        config['llm'] = app_helper.config['service']['llm']
        logger.debug(f"config['llm']:\n{config['llm']}")
        llm_agent = LlmService(config)
        llm_agent.start_process()
        app_helper.wait_agent(llm_agent)

