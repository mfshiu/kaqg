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
from services.kg_service import Topic as KgTopic
from services.llm_service import LlmService

from evaluation.features import ScqFeatures
from evaluation.scq_evaluator import ScqEvaluator
from generation.ranker.node_ranker import NodeRanker
from generation.ranker.simple_ranker import SimpleRanker
from generation.ranker.weighted_ranker import WeightedRanker
from knowsys.knowledge_graph import KnowledgeGraph



class SingleChoiceGenerator(Agent):
    TOPIC_CREATE = "Create/SCQ/Generation"


    def __init__(self, config:dict):
        logger.info(f"config: {config}")
        super().__init__(name='scq.generation.wp', agent_config=config)


    def on_activate(self):
        logger.verbose(f"on_activate")
        self.subscribe(SingleChoiceGenerator.TOPIC_CREATE, topic_handler=self.handle_create)


    def handle_create(self, topic, pcl:TextParcel):
        # question_criteria = {
        #     'question_id': 'Q101',              # 使用者自訂題目 ID
        #     'subject':  'Subject Name',         # 科目名稱
        #     'document': 'Book Name',            # 教材名稱
        #     'section': ['chapter1', 'ch1-1'],   # 指定章節
        #     'difficulty': 50,                   # 難度 30, 50, 70
        # }
        question_criteria = pcl.content
        logger.debug(f"question_criteria: {question_criteria}")
        
        generated = self.generate_question(question_criteria)
        while not self.evaluate_question(generated):
            logger.info(f"Retrying question generation...")
            generated = self.generate_question(question_criteria)

        logger.debug(f"generated_question: {generated}")
        return generated
    
    
    def test_return(self, question_criteria):
        question = {
            'type': 'SCQ',
            'stem': 'The question stem',
            'options': ['option1', 'option2', 'option3', 'option4'],
            'answer': 1,
            'question_criteria': question_criteria
        }
        return question


    def generate_question(self, question_criteria):
        assessment = {
            'question_criteria': question_criteria,
        }
        qc = question_criteria

        # From question criteria to concepts
        subject, document, section = qc['subject'], qc['document'], qc['section']
        pcl = TextParcel({'kg_name': subject, 'document': document, 'section': section})
        concepts = self.publish_sync(KgTopic.CONCEPTS_QUERY.value, pcl).content['concepts']
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
        logger.verbose(f"assessment: {assessment}")
        
        prompt_text = f"""
I have a Single Choice Question (SCQ) in the following JSON structure:

{{
  "stem": "Your question text",
  "option_A": "Option A text",
  "option_B": "Option B text",
  "option_C": "Option C text",
  "option_D": "Option D text",
  "answer": "Correct answer letter"
}}

Please evaluate this SCQ according to the feature keys and levels below. Then, provide **only** the final evaluation result in JSON format (e.g., {{"stem_length": 1, "stem_technical_term_density": 2, ...}}), with no additional text or explanation.

**Feature Keys and Levels**:

1. **stem_technical_term_density**
   - 1: Few or no technical terms (0 to 2 terms)
   - 2: Moderate number of technical terms (2 to 4 terms)
   - 3: Many technical terms (more than 3 terms)

2. **stem_cognitive_level**
   - 1: Only requires memorization of knowledge points
   - 2: Requires understanding and synthesis
   - 3: Requires analysis, synthesis, or evaluation

3. **option_average_length**
   - 1: Short option text (1 to 5 characters)
   - 2: Medium option text (3 to 8 characters)
   - 3: Long option text (more than 5 characters)

4. **option_similarity**
   - 1: Low similarity between options (below 30%)
   - 2: Moderate similarity (around 45%)
   - 3: High similarity (above 60%)

5. **stem_option_similarity**
   - 1: Low relevance between stem and options (below 30%)
   - 2: Moderate relevance (around 45%)
   - 3: High relevance (above 60%)

6. **high_distractor_count**
   - 1: Includes 1 highly attractive distractor
   - 2: Includes 2 highly attractive distractors
   - 3: Includes more than 3 highly attractive distractors

**Instructions**:
1. Read the SCQ from the JSON input.
2. Evaluate each of the seven features using the guidelines above.
3. Output the result in JSON format using the exact keys shown, e.g.:
   {{
     "stem_technical_term_density": 2,
     "stem_cognitive_level": 3,
     "option_average_length": 1,
     ...
   }}

No additional explanation or text is needed—only the evaluation JSON.
"""

        evaluated = self.publish_sync(ScqEvaluator.TOPIC_EVALUATE, TextParcel(assessment))
        logger.debug(f"evaluated: {evaluated}")
        
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

        return dict(zip(ScqFeatures.keys, valid_combination))


    def _generate_features_prompt(self, combination):
        """
        Automatically generates a question description based on parameter scores and feature table.
        :param parameters: A dictionary containing scores for 7 features
        :return: Question description
        """
        keys = ScqFeatures.keys
        titles = ScqFeatures.titles
        descs = ScqFeatures.level_descriptions

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
        bolt_url = self.publish_sync(KgTopic.ACCESS_POINT.value, pcl).content['bolt_url']
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
    agent = SingleChoiceGenerator(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
