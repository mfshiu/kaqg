# Required when executed as the main program.
import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from itertools import product
import json
import re
import random

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel
from services.llm_service import LlmService

from evaluation.features import ScqFeatures



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
            stem = (stem or "").strip()

            # 中文字：每一個 CJK 字元算 1
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', stem)
            chinese_count = len(chinese_chars)

            # 英文單字：連續英文字母視為 1 個 word
            english_words = re.findall(r'[a-zA-Z]+', stem)
            english_word_count = len(english_words)

            # 總資訊長度 = 中文字數 + 英文單字數（標點自然不算）
            total_units = chinese_count + english_word_count

            # 判斷主語言：中文字數 >= 英文單字數 → 視為中文題
            is_chinese = chinese_count >= english_word_count

            if is_chinese:
                # 中文題：以 total_units 套用中文門檻
                if total_units <= 15:
                    return 1
                elif total_units <= 30:
                    return 2
                else:
                    return 3
            else:
                # 英文題：以 total_units 套用英文門檻
                if total_units <= 10:
                    return 1
                elif total_units <= 20:
                    return 2
                else:
                    return 3

        stem = assessment["question"]["stem"]
        grade = grade_stem_length(stem)
        logger.debug(
            f"[stem_length] grade={grade}, stem='{stem}'"
        )
        return grade
    

    def _evaluate_2_to_7(self, assessment):
        question_str = json.dumps(assessment['question'], ensure_ascii=False)
        logger.verbose(f"question_str: {question_str}") 
        user_content = f"""Evaluate the following Single Choice Question (SCQ). Use ONLY the SCQ content for your judgment.

SCQ:
{question_str}

Score the SCQ on the six features below. For each feature, assign a score of 1, 2, or 3 based on its definition.

1. stem_technical_term_density
  Rate how many technical terms appear in the question stem.
  - 1 = Few (0–2 terms)  
  - 2 = Moderate (3–4 terms)  
  - 3 = Many (5 or more)

2. stem_cognitive_level  
   Determine the cognitive level of the stem based on Bloom’s taxonomy.  
   - 1 = Recall (remembering facts)  
   - 2 = Understanding (conceptual comprehension)  
   - 3 = Analysis/Evaluation (critical reasoning)

3. option_average_length  
   Evaluate the average length of the options.  
   - 1 = Short (1–4 words)  
   - 2 = Medium (5–8 words)  
   - 3 = Long (9 or more words)

4. option_similarity  
   Assess similarity among the options in wording or meaning.  
   - 1 = Low similarity  
   - 2 = Moderate similarity  
   - 3 = High similarity

5. stem_option_similarity  
   Evaluate how relevant the options are to the stem.  
   - 1 = High relevance  
   - 2 = Moderate relevance  
   - 3 = Low relevance

6. high_distractor_count  
   Count plausible (attractive but incorrect) distractors.  
   - 1 = 1 strong distractor  
   - 2 = 2 strong distractors  
   - 3 = 3 strong distractors

Return ONLY a JSON object in the following format:
{{
    "stem_technical_term_density": 0,
    "stem_cognitive_level": 0,
    "option_average_length": 0,
    "option_similarity": 0,
    "stem_option_similarity": 0,
    "high_distractor_count": 0
}}
"""
        # logger.debug(f"user_content:\n{user_content}")
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an exam question evaluator. "
                    "Evaluate the SCQ strictly according to the scoring rules provided. "
                    "Use only the SCQ content itself. "
                    "Return ONLY a JSON object with the required keys and numeric scores. "
                    "Do NOT include explanations, comments, or additional text."
                )
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


    def evaluate(self, assessment):
        feature_grades = {}
        feature_grades[ScqFeatures.keys[0]] = self._evaluate_1(assessment)
        feature_grades.update(self._evaluate_2_to_7(assessment))

        return feature_grades

    

if __name__ == '__main__':
    agent = ScqEvaluator(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
