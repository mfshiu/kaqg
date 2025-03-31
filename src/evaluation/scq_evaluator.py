# Required when executed as the main program.
import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from itertools import product
import json
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
        return evaluated
    
    
    def get_test_result(self, assessment):
        feature_grades = {key: random.randint(1, 3) for key in ScqFeatures.keys}
        assessment['features'] = feature_grades
        
        return assessment


    def evaluate(self, assessment):
        return self.get_test_result(assessment)
        qc = assessment['question_criteria']

        # From question criteria to concepts
        subject, document, section = qc['subject'], qc['document'], qc['section']
        pcl = TextParcel({'kg_name': subject, 'document': document, 'section': section})
        concepts = self.publish_sync(Topic.CONCEPTS_QUERY.value, pcl).content['concepts']
        logger.debug(f"concepts: {', '.join([n['name'] for n in concepts])}")
        if not concepts:
            logger.error(msg := f"No concepts found.")
            assessment['error'] = msg
            return assessment

        # Generate text materials
        ranker = SimpleRanker(self, subject, document, section)
        # ranker = WeightedRanker(self, qc['subject'], qc['document'], qc['section'])
        text_materials = []
        for _ in range(10):
            core_concept = ranker.rank_concepts(concepts)
            facts = ranker.rank_facts(core_concept)
            logger.verbose(f"facts: {', '.join([n['name'] for n in facts])}")
            if not facts:
                continue

            text_materials.extend(self._generate_text_materials(subject, facts))
            if len(text_materials) >= 10:
                break
            
        logger.debug(f"text_materials: {text_materials}")
        if not text_materials:
            logger.error(msg := f"No text materials found.")
            assessment['error'] = msg
            return assessment
        
        # Make question
        maked = self._make_question(text_materials, question_criteria['difficulty'])
        
        assessment['question'] = maked
        return assessment
        # return self.test_return(question_criteria)

    
    def evaluate_question(self, assessment):
        logger.debug(f"assessment: {assessment}")
        return not assessment.get('error') and assessment.get('question')
        
        
    def choice_concept(self, concept_nodes):
        return random.choice(concept_nodes)
    
    
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

        keys = [
            "stem_length",
            "stem_technical_term_density",
            "stem_cognitive_level",
            "option_average_length",
            "option_similarity",
            "stem_option_similarity",
            "high_distractor_count",
        ]

        return dict(zip(keys, valid_combination))


    def _generate_features_prompt(self, combination):
        """
        Automatically generates a question description based on parameter scores and feature table.
        :param parameters: A dictionary containing scores for 7 features
        :return: Question description
        """
        descs = [
            ["Short stem length (10 to 25 characters)", "Medium stem length (15 to 35 characters)", "Long stem length (over 20 characters)"],
            ["Few or no technical terms in stem (0 to 2 terms)", "Moderate number of technical terms in stem (2 to 4 terms)", "Many technical terms in stem (more than 3 terms)"],
            ["Only requires memorization of knowledge points", "Requires understanding and synthesis of knowledge points", "Requires analysis, synthesis, or evaluation"],
            ["Short option text (1 to 5 characters)", "Medium option text (3 to 8 characters)", "Long option text (more than 5 characters)"],
            ["Low similarity between options (below 30%)", "Moderate similarity between options (around 45%)", "High similarity between options (above 60%)"],
            ["Low relevance between stem and options (below 30%)", "Moderate relevance between stem and options (around 45%)", "High relevance between stem and options (above 60%)"],
            ["Includes 1 highly attractive distractor", "Includes 2 highly attractive distractors", "Includes more than 3 highly attractive distractors"]
        ]
        keys = [
            "stem_length",
            "stem_technical_term_density",
            "stem_cognitive_level",
            "option_average_length",
            "option_similarity",
            "stem_option_similarity",
            "high_distractor_count"
        ]
        titles = [
            "Stem Length",
            "Technical Term Density in Stem",
            "Cognitive Level",
            "Average Option Length",
            "Option Similarity",
            "Stem-Option Similarity",
            "Number of High-Attraction Distractors"
        ]

        prompt = (f'{titles[i]}: {descs[i][combination[keys[i]] - 1]}' for i in range(7))
        return prompt


    def _chat(self, prompt_text):
        messages = [
            {"role": "system", "content": "You are a helpful exam question generator. 你所建立的題目為單選題，答案只有一個。 Please provide your response with 繁體中文 in JSON format."},
            {"role": "user", "content": f"{prompt_text}\nPlease provide your response in JSON format."}
        ]
        
        response_format = {
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
            'messages': messages,
            'response_format': response_format,
        }
        
        pcl = TextParcel(params)
        question = self.publish_sync(LlmService.TOPIC_LLM_PROMPT, pcl)
        return json.loads(question.content['response'])


    def __shuffle_question(self, question):
        # Extract original options
        original_options = {
            "A": question["option_A"],
            "B": question["option_B"],
            "C": question["option_C"],
            "D": question["option_D"]
        }
        correct_answer_text = original_options[question["answer"]]

        # Shuffle options
        shuffled_items = list(original_options.items())
        random.shuffle(shuffled_items)

        # Build new question structure
        new_question = {
            "stem": question["stem"]
        }

        for idx, (_, text) in enumerate(shuffled_items):
            key = chr(ord("A") + idx)
            new_question[f"option_{key}"] = text
            if text == correct_answer_text:
                correct_new_key = key

        new_question["answer"] = correct_new_key
        return new_question

    def _make_question(self, text_materials, difficulty):
        # Eddie
        # difficulty: 30, 50, 70
        # 丙：10分 for difficulty 30
        # 乙：14分 for difficulty 50
        # 甲：18分 for difficulty 70
        # 隨機取得一組符合條件的 7 個參數組合，考慮各參數的權重。
        # 每個參數的分數為 1, 2, 3，且加權總和需落在 S ± 1 的範圍內。
        # 權重分配：- stem_cognitive_level：1.5 - high_distractor_count：1.2 - 其他特徵：1

        difficulty_mapping = {
            30: 10,
            50: 14,
            70: 18
        }
        
        score = difficulty_mapping[difficulty]
        combination = self._get_weighted_combination(score)
        features = self._generate_features_prompt(combination)
        
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
        question = self._chat(prompt_text)
        logger.info(f"type:{type(question)}, question: {question}")
        return self.__shuffle_question(question)
    
    
    def _generate_text_materials(self, subject, fact_nodes):
        def generate_text_from_paths(records):
            """
            從每個 record 取得路徑 (path)，
            提取 (start_node)-[rel]->(end_node) 組成文字描述。
            """
            text_segments = set()
            for record in records:
                path = record["p"] 
                for rel in path.relationships:
                    start_node = rel.start_node
                    end_node = rel.end_node
                    
                    s_id = start_node.get("name", "(unknown)") 
                    e_id = end_node.get("name", "(unknown)") 
                    r_type = rel.type
                    text_segments.add(f"{s_id}{r_type}{e_id}")

            texts = list(text_segments)
            logger.verbose(f"text_segments: {texts}")
            return texts


        query = """
            MATCH p = (start:fact)-[*1..1]-(other:fact)
            WHERE elementId(start) = $start_element_id
            RETURN p
        """
        pcl = TextParcel({'kg_name': subject})
        bolt_url = self.publish_sync(Topic.ACCESS_POINT.value, pcl).content['bolt_url']
        text_materials = []
        with KnowledgeGraph(uri=bolt_url) as kg:
            with kg.session() as session:
                for fact in fact_nodes:
                    results = session.run(query, start_element_id=fact['element_id'])
                    text_materials.extend(generate_text_from_paths(results))

        return text_materials
        # return [
        #     "104 年全國各縣市焚化底渣產量約占焚化量之 15%",
        #     "104 年度一般廢棄物底渣再利用量占該年度底渣總量之89.3%",
        #     "基隆市、臺北市、新北市、桃園市、新竹市、苗栗縣、臺中市、彰化縣、嘉義市、嘉義縣、臺南市、高雄市、屏東縣等，已將所轄焚化廠底渣委外再利用"
        # ]
            


if __name__ == '__main__':
    agent = ScqEvaluator(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
