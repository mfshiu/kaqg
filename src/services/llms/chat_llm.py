# Required when executed as the main program.
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from langchain_openai import ChatOpenAI
import os

from services.llms.base_llm import BaseLLM



class ChatLLM(BaseLLM):
    _default_params = {
        'model': 'gpt-4o-mini',
        'temperature': 0,
        'streaming': True,
        'prompt': "Say the prompt message is empty!",
        'openai_api_key': "",
    }


    def __init__(self, params:dict):
        self.params = ChatLLM._default_params.copy()  
        self.params.update(params)

        self.openai_api_key = self.params.get('openai_api_key')
        self.model = self.params.get('model', 'gpt-4o-mini')
        self.prompt = self.params.get('prompt', "Say the prompt message is empty!")

        self.chat_model = ChatOpenAI(
            model_name=self.model,
            openai_api_key=self.openai_api_key,
            temperature=self.params.get('temperature', 0),
            streaming=self.params.get('streaming', True)
        )


    def generate_response(self, prompt=None):
        if prompt:
            self.prompt = prompt
        return self.chat_model.invoke(self.prompt).content



if __name__ == '__main__':
    params = {
        'openai_api_key': app_helper.config['service']['llm']['openai_api_key'],
        'model': 'gpt-3.5-turbo',
        'prompt': "Hello, how are you?",
        }
    llm = ChatLLM(params)
    print(llm.generate_response())
