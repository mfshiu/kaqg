import os, sys
import argparse
from itertools import product
import random
from openai import OpenAI
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])



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


    def _get_one_weighted_combination(self, score):
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

        # 隨機選取一組並命名參數
        selected = valid_combination
        result = {
            "stem_length": selected[0],
            "stem_technical_term_density": selected[1],
            "stem_cognitive_level": selected[2],
            "option_average_length": selected[3],
            "option_similarity": selected[4],
            "stem_option_similarity": selected[5],
            "high_distractor_count": selected[6],
        }
        return result
    
    
    def _generate_prompt(self, parameters):
        """
        根據參數分數和特徵表，自動生成出題敘述。
        :param parameters: 包含 7 個特徵的分數，格式為字典
        :return: 題目敘述
        """
        descs = [["題幹字數較短（10 至 25 字）", "題幹字數中等（15 至 35 字之間）", "題幹字數較長（超過 20 字）"],
                ["題幹使用較少或無專業術語（0 至 2 個）", "題幹有適當的專業術語（2 至 4 個）", "題幹使用了較多專業術語（3 個以上）"],
                ["僅需記憶知識點", "涉及知識點的理解與綜合", "需進行分析、綜合或評估"],
                ["選項文字較短（1 至 5 字）", "選項文字中等（3 至 8 字之間）", "選項文字較長（5 字以上）"],
                ["選項間相似度較低（30% 以下）", "選項間相似度適中（45% 左右）", "選項間有較高相似度（60% 以上）"],
                ["題幹與選項內容相關性較低（30% 以下）", "題幹與選項內容相關性適中（45% 左右）", "題幹與選項內容高度相關（60% 以上）"],
                ["包含 1 個高誘答選項", "包含 2 個高誘答選項", "包含 3 個以上的高誘答選項"]]
        keys = ["stem_length", "stem_technical_term_density", "stem_cognitive_level", "option_average_length", "option_similarity", "stem_option_similarity", "high_distractor_count"]
        titles = ["題幹字數", "題幹專業詞密度", "認知程度", "選項平均字數", "選項間相似度", "題幹與選項相似度", "高誘答選項數"]
        
        prompt = (f'{titles[i]}：{descs[i][parameters[keys[i]] - 1]}' for i in range(7))
        return prompt  

    
    def _chat(self, message):
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
                {"role": "system", "content": "You are a helpful assistant. Please provide your response in JSON format."},
                {"role": "user", "content": message + " Please provide your response in JSON format."}
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
    
    def generate_scq(self, score, text)-> dict:
        parameter = self._get_one_weighted_combination(score)
        features = self._generate_prompt(parameter)
        
        prompt_test =  """
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

                        Features:{}

                        Text:{}
                        """.format(features, text)
        answer_concept_and_fact = self._chat(message=prompt_test)
        json_response = json.loads(answer_concept_and_fact)
        return json_response
    

if __name__ == "__main__":
    tripletes = f"""廢棄物超過環境承載力

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

    res = generator.generate_scq(score, tripletes)
    print(res)


