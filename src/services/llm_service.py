# Required when executed as the main program.
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from enum import Enum, auto
import time

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel
from services.llms.chat_llm import BaseLLM, ChatLLM


class LlmModel(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    ChatGPT = auto()
    Claude = auto()
    LLama = auto()



class LlmService(Agent):
    SERVICE_NAME = 'llm_service.services.wastepro'
    TOPIC_LLM_PROMPT = "Prompt/LlmService/Services"

    _default_llm_params = {
        'llm': LlmModel.ChatGPT,
    }


    @staticmethod
    def _generate_llm_model(llm_params=None):
        params = LlmService._default_llm_params.copy()
        if llm_params:
            params.update(llm_params)

        if params['llm'] == LlmModel.ChatGPT:
            llm = ChatLLM(params)
        elif params['llm'] == LlmModel.Claude:
            llm = ChatLLM(params)
        elif params['llm'] == LlmModel.LLama:
            llm = ChatLLM(params)
        else:
            llm = ChatLLM(params)
        
        return llm
    
    
    def __init__(self, agent_config, llm_params=None):
        logger.debug(f"{LlmService.__name__}.{self.__init__.__name__}")
        super().__init__(LlmService.SERVICE_NAME, agent_config)
        self.llm_params = llm_params


    def on_activate(self):
        self.llm:BaseLLM = LlmService._generate_llm_model(self.llm_params)
    

    def on_connected(self):
        self._subscribe(LlmService.TOPIC_LLM_PROMPT, "str", self.handle_prompt)


    def handle_prompt(self, topic:str, pcl:TextParcel):
        prompt_info = pcl.content
        logger.error(f"prompt_info: {prompt_info}")

        response = self.llm.generate_response(prompt_info.get('prompt'))
        logger.debug(self.M(response))

        return {
            'response': response,
        }



if __name__ == '__main__':
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=app_helper.get_agent_config())


        def on_connected(self):
            time.sleep(1)

            self._subscribe(self.agent_id)
            
            pcl = TextParcel({
                'prompt': "現在的美國總統是誰？",
                }, topic_return=self.agent_id)
            logger.error(self.M(f"pcl: {pcl}"))
            self._publish(LlmService.TOPIC_LLM_PROMPT, pcl)


        def on_message(self, topic:str, pcl:TextParcel):
            logger.error(self.M(f"topic: {topic}"))
            logger.error(f"pcl:\n{pcl}")

            # self.terminate()
            # llm_agent.terminate()


    llm_param = {
        # 'model': 'gpt-4o-mini',
        # 'temperature': 0,
        # 'streaming': True,
        # 'prompt': "Say the prompt message is empty!",
        'openai_api_key': "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",
    }
    llm_agent = LlmService(app_helper.get_agent_config(), llm_param)
    llm_agent.start_process()

    ValidationAgent().start_thread()

    app_helper.wait_agent(llm_agent)
