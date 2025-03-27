import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from openai import OpenAI
from services.llms.base_llm import BaseLLM
import json


class ChatLLM(BaseLLM):
    _default_params = {
        'model': 'gpt-4o-mini',
        'response_format': 'text',  # 'text' or dict (function-calling format)
        'temperature': 0,
        'streaming': False,
        'openai_api_key': "",
    }


    def __init__(self, params: dict):
        self.params = ChatLLM._default_params.copy()
        self.params.update(params)

        self.model = self.params.get('model')
        self.response_format = self.params.get('response_format')
        self.temperature = self.params.get('temperature')
        self.streaming = self.params.get('streaming')
        self.api_key = self.params.get('openai_api_key')

        self.client = OpenAI(api_key=self.api_key)


    def generate_response(self, params):
        """
        Generate a response from an OpenAI chat model.

        Args:
            params (str | list[dict] | dict): 
                - If str: treated as a single prompt.
                - If list of dicts: treated as a messages array.
                - If dict: should include a 'messages' key and optionally other settings 
                like 'model', 'temperature', etc.

        Returns:
            str: The generated response text (streamed or full depending on settings).
        """
        if isinstance(params, str):
            # prompt text only
            messages = [{"role": "user", "content": params}]
            params = {'messages': messages}
        elif isinstance(params, list) and isinstance(params[0], dict):
            # messages list only
            messages = params
            params = {'messages': messages}
        elif isinstance(params, dict):
            # must contains 'messages' key
            messages = params['messages']
        else:
            raise ValueError("Invalid input.")

        kwargs = {
            "model": params.get('model', self.model),
            "messages": messages,
            "response_format": params.get('response_format', self.response_format),
            "temperature": params.get('temperature', self.temperature),
            "stream": params.get('streaming', self.streaming),
        }

        response = self.client.chat.completions.create(**kwargs)

        if self.streaming:
            result = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    result += chunk.choices[0].delta.content
            return result
        else:
            choice = response.choices[0]
            return choice.message.content


if __name__ == '__main__':
    prompt_text = "Please create a question about the water cycle."
    
    messages=[
        {"role": "system", "content": "You are a helpful exam question generator. Please provide your response in JSON format."},
        {"role": "user", "content": f"{prompt_text}\nPlease provide your response in JSON format."}
    ]
    
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "generate_question",
            "schema": {
                "type": "object",
                "properties": {
                    "stem": {"type": "string"},
                    "option_A": {"type": "string"},
                    "option_B": {"type": "string"},
                    "option_C": {"type": "string"},
                    "option_D": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": [
                    "stem",
                    "option_A",
                    "option_B",
                    "option_C",
                    "option_D",
                    "answer"
                ],
                "additionalProperties": False
            }
        }
    }
    
    params = {
        'openai_api_key': app_helper.config['service']['llm']['openai_api_key'],
        'model': 'gpt-4o-mini',
        'response_format': response_format,
        'streaming': False,
    }

    llm = ChatLLM(params)
    # messages = "Please create a question about the water cycle."
    # result = llm.generate_response(messages)
    params['messages'] = messages
    result = llm.generate_response(params)
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)
