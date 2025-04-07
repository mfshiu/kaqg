# Required when executed as the main program.
import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from itertools import product
import json
import math
import random

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel
from services.kg_service import Topic
from services.llm_service import LlmService

from evaluation.features import ScqFeatures
from generation.ranker.node_ranker import NodeRanker
from generation.ranker.simple_ranker import SimpleRanker
from generation.ranker.weighted_ranker import WeightedRanker
from knowsys.knowledge_graph import KnowledgeGraph



class ScqEvaluator(Agent):
    TOPIC_EVALUATE = "Evaluate/SCQ/Evaluation"


    def __init__(self, config:dict):
        logger.debug(f"config: {config}")
        super().__init__(name='scq.evaluation.wp', agent_config=config)


    def on_activate(self):
        logger.verbose(f"on_activate")
        self.subscribe(ScqEvaluator.TOPIC_EVALUATE, topic_handler=self.handle_evaluate)


    def handle_evaluate(self, topic, pcl:TextParcel):
        # Example of pcl.content:
        # {
        #     "question_criteria": {
        #         "question_id": "Q1743158893",
        #         "subject": "W0301",
        #         "section": [
        #             "貳、廢棄物清理專業技術人員相關法規及其職掌"
        #         ],
        #         "document": "Wastepro02",
        #         "difficulty": 50
        #     },
            # "question": {
            #     "stem": "根據環境保護專責及技術人員訓練管理辦法，情節嚴重的違規行為應依據哪一條款處理？",
            #     "option_A": "第30條第3款",
            #     "option_B": "第15條第1款",
            #     "option_C": "第26條第4款",
            #     "option_D": "第10條第2款",
            #     "answer": "C"
            # }
        # }
        assessment = pcl.content
        logger.debug(f"assessment: {assessment}")
        
        evaluated = self.evaluate(assessment)
        logger.debug(f"evaluated result: {evaluated}")
        assessment['evaluation'] = evaluated
        
        return assessment
    
    
    def get_test_result(self, assessment):
        feature_grades = {key: random.randint(1, 3) for key in ScqFeatures.keys}
        assessment['features'] = feature_grades
        
        return assessment


    def _evaluate_1(self, assessment):
        def grade_stem_length(stem: str) -> int:
            length = len(stem)
            if length < 10:
                return 1  # 長度過短，不分級
            elif length > 35:
                return 3

            ## 計算與各中心的距離轉為權重
            # 模糊分級中心點
            centers = {
                1: 15,  # Short
                2: 25,  # Medium
                3: 35   # Long
            }
            sigma = 4  # 控制模糊程度，越小越敏感
            # 計算與各中心的距離轉為權重
            weights = {
                k: math.exp(-((length - c) ** 2) / (2 * sigma ** 2))
                for k, c in centers.items()
            }

            # 使用權重進行隨機選擇
            grades = list(weights.keys())
            probs = list(weights.values())
            selected = random.choices(grades, weights=probs, k=1)[0]
            
            return selected
        
        stem = assessment['question']['stem']
        grade = grade_stem_length(stem)
        logger.debug(f"grade: {grade}, len: {len(stem)}, stem: {stem}")
        return grade
        # return random.randint(1, 3)
    

    def _evaluate_2_to_7(self, assessment):
        question_str = json.dumps(assessment['question'], ensure_ascii=False)
        logger.verbose(f"question_str: {question_str}")
        user_content = f"""I have a Single Choice Question (SCQ) in the following JSON structure:
{question_str}

Evaluate the SCQ using these features:
- stem_technical_term_density: 1 = few or no technical terms, 2 = moderate, 3 = many
- stem_cognitive_level: 1 = memorization, 2 = understanding, 3 = analysis or evaluation
- option_average_length: 1 = short (1–5 chars), 2 = medium (3–8), 3 = long (more than 5)
- option_similarity: 1 = low similarity (<30%), 2 = moderate (~45%), 3 = high (>60%)
- stem_option_similarity: 1 = low relevance, 2 = moderate, 3 = high
- high_distractor_count: 1 = 1 strong distractor, 2 = 2, 3 = more than 3

Return only a JSON object like this:
{{
    "stem_technical_term_density": 2,
    "stem_cognitive_level": 3,
    "option_average_length": 1,
    "option_similarity": 2,
    "stem_option_similarity": 3,
    "high_distractor_count": 2
}}
"""
        messages = [
            {
                "role": "system",
                "content": "You are a helpful exam question evaluator. Please evaluate the question according to the feature keys and levels provided. Only return your response in JSON format."
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "evaluate_question",
                "schema": {
                    "type": "object",
                    "properties": {
                        key: {"type": "integer", "minimum": 1, "maximum": 3}
                        for key in ScqFeatures.keys[1:]
                    },
                    "required": list(ScqFeatures.keys[1:]),
                    "additionalProperties": False
                }
            }
        }
        params = {
            'messages': messages,
            'response_format': response_format,
        }
        pcl = TextParcel(params)
        evaluation = self.publish_sync(LlmService.TOPIC_LLM_PROMPT, pcl)
        evaluation_result = json.loads(evaluation.content['response'])
        logger.debug(f"evaluation_result: {evaluation_result}")
        
        return evaluation_result
        # return {key: random.randint(1, 3) for key in ScqFeatures.keys[1:]}


    def evaluate(self, assessment):
        feature_grades = {}
        feature_grades[ScqFeatures.keys[0]] = self._evaluate_1(assessment)
        feature_grades.update(self._evaluate_2_to_7(assessment))

        return feature_grades

    

if __name__ == '__main__':
    agent = ScqEvaluator(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
