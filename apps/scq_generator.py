import os, sys
from itertools import product
import random
from openai import OpenAI
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])

from evaluation.features import ScqFeatures



class GetSCQGeneratorPrompt:
    def __init__(self, api_key, model="gpt-4o-mini"):
        """
        Initialize the GPT chat client.
        
        Args:
            api_key (str): OpenAI API key
            model (str): Name of the GPT model to use
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model


    def _get_weighted_combination(self, score):
        """
        隨機取得一組符合條件的 7 個參數組合，考慮各參數的權重。
        每個參數的分數為 1, 2, 3，且加權總和需落在 S ± 1 的範圍內。

        權重分配：
        - stem_cognitive_level：1.5
        - high_distractor_count：1.2
        - 其他特徵：1

        :param score: 目標總分
        :return: 一組符合條件的參數組合，對應七個具體描述
        """
        
        weights = [1, 1, 1.5, 1, 1, 1, 1.2] # 定義各參數的權重  
        down_score, up_score = score - 1, score + 1
        if up_score < (sw:=sum(weights)) or down_score > sw * 3:
            return [0] * 7
        
        all_comnination = list(product(range(1, 4), repeat=7))
        random.shuffle(all_comnination)

        # 篩選符合條件的組合
        valid_combination = None
        for combination in all_comnination:
            weighted_sum = sum(x * w for x, w in zip(combination, weights))
            if down_score <= weighted_sum <= up_score:
                valid_combination = combination
                break

        keys = ScqFeatures.keys

        return dict(zip(keys, valid_combination))
    
    
    def _generate_features_prompt(self, parameters):
        """
        Automatically generates a question description based on parameter scores and feature table.
        :param parameters: A dictionary containing scores for 7 features
        :return: Question description
        """
        descs = ScqFeatures.level_descriptions
        keys = ScqFeatures.keys
        titles = ScqFeatures.titles

        prompt = (f'{titles[i]}: {descs[i][parameters[keys[i]] - 1]}' for i in range(len(keys)))
        return prompt


    def _chat(self, prompt_text):
        """
        Send a message to the GPT model and get the response.
        
        Args:
            message (str): Input message to send to the model
            
        Returns:
            str: Response from the model
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful exam question generator. Please provide your response in JSON format."},
                {"role": "user", "content": f"{prompt_text}\nPlease provide your response in JSON format."}
            ],
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
            },
            stream=False
        )
        return response.choices[0].message.content
    
    
    def generate_scq(self, score, text_materials)-> dict:
        parameter = self._get_weighted_combination(score)
        
        from evaluation import scq_feature_criteria
        features = self._generate_features_prompt(parameter)
        
        prompt_text =  f"""
You are an exam question creator tasked with generating multiple-choice questions based on the given features and text. Follow these instructions carefully:
1.Create single-answer multiple-choice questions (4 options: A, B, C, D).
2.Include the correct answer and ensure the correct option is distributed randomly (not concentrated in A).
3.Do not provide explanations or analysis of the questions or answers.
4.Output the result in a table format with the following headers:
    - Stem
    - Option A
    - Option B
    - Option C
    - Option D
    - Answer (only indicate the correct option: A, B, C, or D).

Features:
{features}

Text:
{text_materials}
"""
        answer_concept_and_fact = self._chat(prompt_text)
        json_response = json.loads(answer_concept_and_fact)
        return json_response
    

if __name__ == "__main__":
    text_materials = f"""廢棄物超過環境承載力

    廢棄物分類為一般廢棄物與事業廢棄物

    事業廢棄物細分為有害事業廢棄物與一般事業廢棄物

    廢棄物經歷貯存、回收、清除與中間處理

    廢棄物最終進入最終處置

    中間處理包括焚化、熱分解、堆肥與厭氧/好氧消化

    最終處置分為陸域處置與水域處置

    陸域處置包括安定掩埋、衛生掩埋與封閉掩埋

    水域處置包括河川湖泊掩埋與海洋棄置

    海洋棄置影響沿海生態並受限於法規規範

    廢棄物處理目標為回收有價物質、回收熱能、生產有機肥料與妥善處理殘渣

    環境污染危害生態系統與人體健康

    法規規範廢棄物處置並保護環境
    """
    score = 15

    # init chatbot
    api_key=app_helper.config['service']['llm']['openai_api_key']
    generator = GetSCQGeneratorPrompt(api_key)

    res = generator.generate_scq(score, text_materials)
    print(res)


