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
            stem_clean = stem.strip()

            # 判斷是否為大多為中文（中英文混雜時以中文為主）
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', stem_clean)
            english_words = re.findall(r'[a-zA-Z]+', stem_clean)

            is_chinese = len(chinese_chars) >= len(english_words)
            if is_chinese:
                length = len(chinese_chars)
                if length <= 15:
                    return 1
                elif length <= 30:
                    return 2
                else:
                    return 3
            else:
                word_count = len(stem_clean.split())
                if word_count <= 10:
                    return 1
                elif word_count <= 20:
                    return 2
                else:
                    return 3
        
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

Evaluate the Single Choice Question (SCQ) based on the following six features. For each feature, assign a score of 1, 2, or 3, using the definitions provided. Your evaluation should be accurate and based only on the SCQ’s content.

1. stem_technical_term_density
  Rate how many technical terms appear in the question stem.
  - 1 = Few or no technical terms (0–2)
  - 2 = Moderate number of technical terms (2–4)
  - 3 = Many technical terms (more than 3)

2. stem_cognitive_level
  Determine the cognitive demand of the stem based on Bloom’s taxonomy.
  - 1 = Memorization (recall of facts)
  - 2 = Understanding or synthesis (conceptual comprehension, combination)
  - 3 = Analysis or evaluation (critical thinking, judgment)

3. option_average_length
  Evaluate the average character length of the options.
  - 1 = Short (1–4 words)
  - 2 = Medium (3–6 words)
  - 3 = Long (more than 5 words)

4. option_similarity
  Assess how similar the options are to each other in wording or meaning.
  - 1 = Low similarity (less than 20%)
  - 2 = Moderate similarity (around 50%)
  - 3 = High similarity (greater than 80%)

5. stem_option_similarity
  Evaluate how closely related the options are to the stem.
  - 1 = High relevance (greater than 80%)
  - 2 = Moderate relevance (around 50%)
  - 3 = Low relevance (less than 20%)

6. high_distractor_count
  Count how many highly attractive distractors (incorrect but plausible options) are included.
  - 1 = 1 strong distractor
  - 2 = 2 strong distractors
  - 3 = Include more than 3 strong distractors
 
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
        # logger.debug(f"user_content:\n{user_content}")
        
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
    

#     def _evaluate_2_to_7(self, assessment):
#         question_str = json.dumps(assessment['question'], ensure_ascii=False)
#         logger.verbose(f"question_str: {question_str}")
#         user_content = f"""I have a Single Choice Question (SCQ) in the following JSON structure:
# {question_str}

# Evaluate the Single Choice Question (SCQ) based on the following six features. For each feature, assign a score of 1, 2, or 3, using the definitions provided. Your evaluation should be accurate and based only on the SCQ’s content.

# 1. stem_technical_term_density  
#    Evaluate the presence of technical terms in the question stem.  
#    Easy: A minimal use of technical terms, with only a few or none at all, making the question easy to comprehend.  
#    Medium: A moderate presence of technical terms, adding some complexity without overwhelming the learner.  
#    Hard: An abundant use of technical terms, challenging the learner and requiring a deep understanding of the subject matter.

# 2. stem_cognitive_level  
#    Assess the cognitive challenge posed by the stem, following Bloom's taxonomy.  
#    Easy: A simple task of remembering basic facts or concepts, requiring only recall.  
#    Medium: A task that goes beyond simple recall, requiring understanding or the synthesis of information.  
#    Hard: A higher-level task that demands analysis, evaluation, or critical thinking, pushing the learner to make informed judgments.

# 3. option_average_length  
#    Determine the average length of the options provided.  
#    Easy: The options should be brief and to the point, offering quick, easy choices for the learner.  
#    Medium: The options should provide a moderate level of detail, balancing brevity with sufficient context for understanding.  
#    Hard: The options should be substantial, providing enough information to challenge the learner's ability to discern the correct answer.

# 4. option_similarity  
#    Evaluate the degree of similarity among the options.  
#    Easy: The options should be clearly distinct, offering no confusion for the learner.  
#    Medium: The options should have some similarities, requiring careful consideration but still easily distinguishable.  
#    Hard: The options should be highly similar, making it difficult for the learner to identify the correct answer without a deep understanding.

# 5. stem_option_similarity  
#    Assess the relevance of the options in relation to the stem.  
#    Easy: The options should closely match the stem's content, making them directly relevant and easy to connect with the question.  
#    Medium: The options should have a moderate relevance, still relating to the stem but leaving some room for thoughtful consideration.  
#    Hard: The options should have minimal relevance, presenting only loose connections to the stem and requiring extra effort to link the two.

# 6. high_distractor_count  
#    Count the number of highly plausible but incorrect options included.  
#    Easy: Only a single, strong distractor should be included, designed to mislead learners who do not fully understand the material.  
#    Medium: Two strong distractors should be included, adding complexity and requiring the learner to carefully evaluate each option.  
#    Hard: More than three strong distractors should be included, making the question challenging and testing the learner’s ability to critically assess all options.
 
# Return only a JSON object like this:
# {{
#     "stem_technical_term_density": 2,
#     "stem_cognitive_level": 3,
#     "option_average_length": 1,
#     "option_similarity": 2,
#     "stem_option_similarity": 3,
#     "high_distractor_count": 2
# }}
# """
#         # logger.debug(f"user_content:\n{user_content}")
        
#         messages = [
#             {
#                 "role": "system",
#                 "content": "You are a helpful exam question evaluator. Please evaluate the question according to the feature keys and levels provided. Only return your response in JSON format."
#             },
#             {
#                 "role": "user",
#                 "content": user_content
#             }
#         ]
#         response_format = {
#             "type": "json_schema",
#             "json_schema": {
#                 "name": "evaluate_question",
#                 "schema": {
#                     "type": "object",
#                     "properties": {
#                         key: {"type": "integer", "minimum": 1, "maximum": 3}
#                         for key in ScqFeatures.keys[1:]
#                     },
#                     "required": list(ScqFeatures.keys[1:]),
#                     "additionalProperties": False
#                 }
#             }
#         }
#         params = {
#             'messages': messages,
#             'response_format': response_format,
#         }
#         pcl = TextParcel(params)
#         evaluation = self.publish_sync(LlmService.TOPIC_LLM_PROMPT, pcl)
#         evaluation_result = json.loads(evaluation.content['response'])
#         logger.debug(f"evaluation_result: {evaluation_result}")
        
#         return evaluation_result
#         # return {key: random.randint(1, 3) for key in ScqFeatures.keys[1:]}


    def evaluate(self, assessment):
        feature_grades = {}
        feature_grades[ScqFeatures.keys[0]] = self._evaluate_1(assessment)
        feature_grades.update(self._evaluate_2_to_7(assessment))

        return feature_grades

    

if __name__ == '__main__':
    agent = ScqEvaluator(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
