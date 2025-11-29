import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from services.llms.base_llm import BaseLLM
import json
import requests

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))


class OssGptLLM(BaseLLM):
    _default_params = {
        'model': 'gpt-oss:20b',
        'temperature': 0,
        'streaming': False,
        'base_url': 'http://140.115.53.67:11436',
    }


    def __init__(self, params: dict):
        self.params = OssGptLLM._default_params.copy()
        self.params.update(params)

        self.model = self.params.get('model')
        self.temperature = self.params.get('temperature')
        self.streaming = self.params.get('streaming')
        self.base_url = self.params.get('base_url')
        self.response_format = self.params.get('response_format', None)


    def generate_response(self, messages):
        kwargs = {
            "model": self.model,
            "temperature": self.temperature,
            "stream": self.streaming,
        }
        
        if isinstance(messages, str):
            # prompt text only
            kwargs['prompt'] = messages
        elif isinstance(messages, list) and isinstance(messages[0], dict):
            # messages list only
            kwargs['messages'] = messages
        elif isinstance(messages, dict):
            kwargs['messages'] = [messages]
        else:
            raise ValueError("Invalid input.")

        # ----------------------------------------------------
        # ⭐ 使用 requests.post 發送請求
        # ----------------------------------------------------
        
        # 1. 根據 kwargs 決定 API 端點 (Endpoint)
        if 'prompt' in kwargs:
            endpoint = "/api/generate"
            kwargs.pop('messages', None)
        elif 'messages' in kwargs:
            endpoint = "/api/chat"
            kwargs.pop('prompt', None)
        else:
            raise ValueError("Missing required parameter 'messages' or 'prompt' in kwargs.")
        
        if not self.base_url:
            raise ValueError("base_url is not set for OssGptLLM")
        api_url = f"{self.base_url.rstrip('/')}{endpoint}"
        
        logger.verbose(f"api_url: {api_url}, kwargs: {kwargs}") # type: ignore
        
        # 2. 發送 HTTP 請求
        try:
            # 這裡使用 requests.post 代替 self.client.chat.completions.create
            response = requests.post(api_url, json=kwargs, stream=kwargs.get('stream', False))
            response.raise_for_status() # 檢查 HTTP 錯誤
        except requests.exceptions.RequestException as e:
            logger.error(f"API Request failed: {e}")
            raise

        # 3. 回應解析 (修改為適應 requests.post 的回傳結構)
        if self.streaming:
            # ⭐ 處理 streaming 模式需要複雜的 JSON chunk 解析，這裡先省略複雜邏輯，回傳錯誤提示
            raise NotImplementedError("Streaming parsing for raw requests API is complex and not fully implemented here.")
        else: 
            # 非 streaming
            result_json = response.json()
            
            if endpoint == "/api/generate":
                # /api/generate 的回覆內容在 "response" 欄位
                return result_json.get("response")
            elif endpoint == "/api/chat":
                # /api/chat 的回覆內容在 ["message"]["content"] 欄位
                return result_json.get("message", {}).get("content")
            raise ValueError(f"Unexpected response structure from API. JSON: {result_json}")

if __name__ == '__main__':
    prompt_text = "請建立一個關於水資源循環的考題。"
    
    # messages=[
    #     {"role": "system", "content": "You are a helpful exam question generator. Please provide your response in JSON format."},
    #     {"role": "user", "content": f"{prompt_text}\nPlease provide your response in JSON format and Chinese."}
    # ]
    messages=[
        {"role": "system", "content": "你是一個專業的出題老師。"},
        {"role": "user", "content": f"{prompt_text}\n請使用 JSON 格式回覆。"}
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
        # 'model': 'gpt-oss:20b',
        'response_format': response_format,
        'streaming': False,
    }

    llm = OssGptLLM(params)
    params['messages'] = messages
    print(f"Input messages: {json.dumps(messages, indent=2)}")
    result = llm.generate_response(params)
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)
