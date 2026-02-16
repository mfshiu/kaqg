# scq_generator.py
# Required when executed as the main program.
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from itertools import product
import json
import random
import re

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
from generation.ranker.wm_ranker import WasteManagementRanker
from knowsys.knowledge_graph import KnowledgeGraph



class SingleChoiceGenerator(Agent):
    TOPIC_CREATE = "Create/SCQ/Generation"
    
    difficulty_mapping = {
        30: 10,
        50: 14,
        70: 18
    }
    # difficulty_mapping = {
    #     30: 12,
    #     50: 14,
    #     70: 16
    # }
    weights = [1, 1, 1.5, 1, 1, 1, 1.2] # 定義各參數的權重  

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

        max_retries = 3
        for attempt in range(max_retries):
            generated = self.generate_question(question_criteria)
            if self._is_valid_question(generated):
                logger.info(f"generated_question: {generated}")
                return generated
            logger.warning(f"Empty or invalid question (attempt {attempt + 1}/{max_retries}), retrying...")
        logger.error("Failed to generate valid question after retries")
        return generated

    def _is_valid_question(self, assessment) -> bool:
        """檢查 assessment 是否包含有效的題目（非空 stem）"""
        if not assessment or not isinstance(assessment, dict):
            return False
        q = assessment.get('question')
        if not q or not isinstance(q, dict):
            return False
        stem = (q.get('stem') or '').strip()
        return bool(stem and not stem.startswith('【系統錯誤】'))

    def handle_create_with_evaluatino(self, topic, pcl:TextParcel):
        # question_criteria = {
        #     'question_id': 'Q101',              # 使用者自訂題目 ID
        #     'subject':  'Subject Name',         # 科目名稱
        #     'document': 'Book Name',            # 教材名稱
        #     'section': ['chapter1', 'ch1-1'],   # 指定章節
        #     'difficulty': 50,                   # 難度 30, 50, 70
        # }
        question_criteria = pcl.content
        logger.debug(f"question_criteria: {question_criteria}")
        
        try_count = 0
        generated_questions = []  # List to store all generated questions with their evaluation results
        grade_criteria = SingleChoiceGenerator.difficulty_mapping[question_criteria['difficulty']]
        passed = False

        while try_count < 3:
            generated = self.generate_question(question_criteria)
            if not generated or not self._is_valid_question(generated):
                logger.warning(f"Empty or invalid question (attempt {try_count + 1}/3), retrying...")
                try_count += 1
                continue
            passed, grade_value = self.evaluate_question(generated, grade_criteria)
            generated_questions.append((generated, passed, grade_value))

            if passed:
                break
            logger.info(f"Retrying question generation...")
            try_count += 1

        # If no question passed after 3 tries, choose the one with the minimum difference between grade_value and grade_criteria
        if not passed and generated_questions:
            best_generated = min(generated_questions, key=lambda x: abs(x[2] - grade_criteria))[0]
            generated = best_generated
        elif not generated_questions:
            # 所有重試皆為空題目，最後一次嘗試
            generated = self.generate_question(question_criteria)

        logger.debug(f"try_count: {try_count}")
        logger.info(f"generated_question: {generated}")
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
            raise ValueError("No concepts found.")
            # logger.error(msg := f"No concepts found.")
            # assessment['error'] = msg
            # return assessment

        # Generate text materials
        ranker = WasteManagementRanker(self, subject, document, section)
        # ranker = SimpleRanker(self, subject, document, section)
        # ranker = WeightedRanker(self, qc['subject'], qc['document'], qc['section'])
        count = question_criteria.get('difficulty', 30) // 3
        text_materials = []
        for _ in range(count):
            core_concept = ranker.rank_concepts(concepts)
            facts = ranker.rank_facts(core_concept)
            logger.verbose(f"facts: {', '.join([n['name'] for n in facts])}")
            if not facts:
                continue

            text_materials.extend(self._generate_text_materials(subject, facts))
            if len(text_materials) >= count:
                break
            
        logger.debug(f"text_materials: {text_materials}")
        if not text_materials:
            raise ValueError("No text materials found.")
            # logger.error(msg := f"No text materials found.")
            # assessment['error'] = msg
            # return assessment
        
        # Make question
        maked, feature_levels = self._make_question(text_materials, question_criteria['difficulty'])
        if maked:
            assessment['question'] = maked
            assessment['question_criteria']['feature_levels'] = feature_levels
            assessment['question_criteria']['weighted_grade'] = sum(x * w for x, w in zip(feature_levels.values(), SingleChoiceGenerator.weights))
            return assessment
        else:
            return None
        # return self.test_return(question_criteria)

    
    def evaluate_question(self, assessment, grade_criteria):
        logger.verbose(f"assessment: {assessment}")
        
        evaluated = self.publish_sync(ScqEvaluator.TOPIC_EVALUATE, TextParcel(assessment))
        logger.debug(f"evaluated: {evaluated.content}")
        
        # grade_criteria = SingleChoiceGenerator.difficulty_mapping[assessment['question_criteria']['difficulty']]
        grades = evaluated.content['evaluation'].values()
        grade_evaluated = sum(x * w for x, w in zip(grades, SingleChoiceGenerator.weights))
        # grade_evaluated = sum(evaluated.content['evaluation'].values())
        passed = abs(grade_criteria - grade_evaluated) <= 1.5
        logger.debug(f"passed: {passed}, grade_criteria: {grade_criteria}, grade_evaluated: {grade_evaluated}")

        return passed, grade_evaluated

        # return not assessment.get('error') and assessment.get('question')
        
        
    def choice_concept(self, concept_nodes):
        return random.choice(concept_nodes)
    
    
    def _get_weighted_combination(self, score):
        """
        Randomly select a set of 7 parameter combinations that meet the conditions, considering the weight of each parameter.
        Each parameter score is 1, 2, or 3, and the weighted sum must fall within the range of S ± 1.

        Weight distribution:  
        - stem_cognitive_level: 1.5  
        - high_distractor_count: 1.2  
        - Other features: 1

        :param score: Target total score  
        :return: A set of parameter combinations that meet the conditions, corresponding to seven specific descriptions
        """
        
        down_score, up_score = score - 1, score + 1
        if up_score < (sw:=sum(SingleChoiceGenerator.weights)) or down_score > sw * 3:
            return [0] * 7

        all_comnination = list(product(range(1, 4), repeat=7))
        random.shuffle(all_comnination)

        # 篩選符合條件的組合
        valid_combination = None
        for combination in all_comnination:
            weighted_sum = sum(x * w for x, w in zip(combination, SingleChoiceGenerator.weights))
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

        prompt = (f'{titles[i]}: {descs[i][combination[keys[i]] - 1]}' for i in range(len(keys)))
        return prompt


    def clean_string(self, s: str) -> str:
        # 判斷是否包含中文
        has_chinese = re.search(r'[\u4e00-\u9fff]', s) is not None

        if has_chinese:
            # 中文：移除所有空白（包含空格、tab、換行）
            return re.sub(r'\s+', '', s)
        else:
            # 非中文：只 trim
            return s.strip()
        

    def _normalize_answer_key(self, answer: str) -> str:
        if not answer:
            return "D"
        a = str(answer).strip().upper()

        mapping = {
            "A": "A", "B": "B", "C": "C", "D": "D",
            "OPTION_A": "A", "OPTION_B": "B",
            "OPTION_C": "C", "OPTION_D": "D",
            "1": "A", "2": "B", "3": "C", "4": "D"
        }
        return mapping.get(a, "D")  # 無法解讀就當 D，避免整個流程爆掉

        
    def _chat(self, prompt_text):
        messages = [
            { "role": "system", "content": ("You are a helpful exam question generator. ...") },
            {
                "role": "user",
                "content": (
                    f"{prompt_text}\n\n"
                    "Based on the features and text materials above, generate ONE single-answer "
                    "multiple-choice question in Traditional Chinese (zh-TW). Return ONLY a valid JSON object "
                    "with the keys: \"stem\", \"option_A\", \"option_B\", \"option_C\", \"option_D\", \"answer\". "
                    "Do NOT wrap the JSON with ``` or any markdown, and do NOT add any extra text."
                )
            }
        ]

        params = { 'messages': messages }

        pcl = TextParcel(params)

        try:
            # 先嘗試呼叫 LLM
            question = self.publish_sync(
                LlmService.TOPIC_LLM_PROMPT,
                pcl,
                timeout=240
            )
        except TimeoutError:
            logger.error("LLM 產生試題逾時")
            # 直接回傳錯誤假題
            return self._build_error_question("LLM 產生試題逾時，請稍後再試。")
        except Exception as e:
            logger.exception(e)
            return self._build_error_question("LLM 呼叫發生未預期錯誤。")

        response = None
        try:
            raw = app_helper.load_json(json_text := question.content['response'])
            # LLM 可能回傳 list（如 [{}]），取第一個有效 dict
            if isinstance(raw, list):
                response = next((x for x in raw if isinstance(x, dict) and x), None)
            elif isinstance(raw, dict) and raw:
                response = raw
            if response:
                response = dict(response)  # 避免修改原始物件
                response['stem'] = self.clean_string(response.get('stem', ''))
                response['option_A'] = self.clean_string(response.get('option_A', ''))
                response['option_B'] = self.clean_string(response.get('option_B', ''))
                response['option_C'] = self.clean_string(response.get('option_C', ''))
                response['option_D'] = self.clean_string(response.get('option_D', ''))

                # ✅ 先正規化 answer，避免出現 "option_C"、"1" 等奇怪值
                raw_ans = response.get('answer', '')
                response['answer'] = self._normalize_answer_key(raw_ans)

                # ✅ 檢查 stem 與選項是否完整，否則直接回錯誤假題
                if not (response.get('stem') or '').strip():
                    logger.error(f"LLM 回傳空題幹: {response}")
                    return self._build_error_question("LLM 回傳空題幹，請稍後再試。")
                if not all(response.get(k, '').strip() for k in
                           ['option_A', 'option_B', 'option_C', 'option_D']):
                    logger.error(f"LLM 回傳選項不完整: {response}")
                    return self._build_error_question("LLM 回傳選項不完整，請稍後再試。")

        except json.JSONDecodeError as e:
            logger.exception(e)
            logger.error(f"Original response: {json_text}")
            # 回傳格式錯誤的假題
            response = self._build_error_question("LLM 回傳格式錯誤，請稍後再試。")
        except Exception as e:
            logger.exception(e)
            response = self._build_error_question("LLM 回應處理失敗，請稍後再試。")

        return app_helper.fix_json_keys(response) if response and isinstance(response, dict) else self._build_error_question("未知錯誤，請稍後再試。")


    def _build_error_question(self, message: str) -> dict:
        """產生一題顯示錯誤用的假題（維持題目 JSON 結構）"""
        msg = self.clean_string(message)
        return {
            "stem": f"【系統錯誤】{msg}（此題僅為占位顯示，請勿作答與納入正式測驗。）",
            "option_A": "系統產生試題逾時或失敗。",
            "option_B": "請重新整理頁面或稍後再試。",
            "option_C": "請聯絡系統管理員以協助處理。",
            "option_D": "以上皆是（此題為錯誤提示用假題）。",
            "answer": "D"  # 隨便給一個合法選項，避免前端壞掉
        }


    def __shuffle_options(self, question):
        try:
            # ✅ 先確保 answer 是 A~D 之一
            answer_key = self._normalize_answer_key(question.get("answer", ""))

            # ✅ 用 get，避免 KeyError；空字串代表 LLM 沒給
            original_options = {
                "A": question.get("option_A", ""),
                "B": question.get("option_B", ""),
                "C": question.get("option_C", ""),
                "D": question.get("option_D", "")
            }

            # 若選項內容不完整，視為錯誤題
            if not all(original_options.values()):
                raise ValueError(f"選項內容不完整: {original_options}")

            correct_answer_text = original_options[answer_key]

            # Shuffle options
            shuffled_items = list(original_options.items())
            random.shuffle(shuffled_items)

            new_question = {
                "stem": question.get("stem", "")
            }
            correct_new_key = "D"  # default 保險值

            for idx, (_, text) in enumerate(shuffled_items):
                key = chr(ord("A") + idx)
                new_question[f"option_{key}"] = text
                if text == correct_answer_text:
                    correct_new_key = key

            new_question["answer"] = correct_new_key
            return new_question

        except Exception as e:
            logger.exception(e)
            # ✅ 任何錯誤都不要讓整個流程爆掉，回錯誤假題
            return self._build_error_question("LLM 回傳試題格式錯誤，請稍後再試。")


    def _make_question(self, text_materials, difficulty):
        # Eddie
        # difficulty: 30, 50, 70
        # 丙：12分 for difficulty 30
        # 乙：14分 for difficulty 50
        # 甲：16分 for difficulty 70
        # 隨機取得一組符合條件的 7 個參數組合，考慮各參數的權重。
        # 每個參數的分數為 1, 2, 3，且加權總和需落在 S ± 1 的範圍內。
        # 權重分配：- stem_cognitive_level：1.5 - high_distractor_count：1.2 - 其他特徵：1

        score = SingleChoiceGenerator.difficulty_mapping[difficulty]
        combination = self._get_weighted_combination(score)
        logger.verbose(f"combination: {combination}")        
        feature_descs = self._generate_features_prompt(combination)
        features_text = '\n'.join(feature_descs)
        # logger.verbose(f"feature_descs: {features_text}")
        
        materials_text = '\n'.join(text_materials[:50])
        
        prompt_text = f"""
You are given feature descriptions and source text for generating an exam question.

Features:
{features_text}

Text materials:
{materials_text}
"""
        logger.verbose(f"prompt_text:\n{prompt_text}") # type: ignore
        question = self._chat(prompt_text)
        if isinstance(question, list):
            question = question[0] if question else None
        logger.info(f"type:{type(question)}, question: {question}")
        if question and (question.get("stem") or "").strip():
            if 'D' != question.get("answer"):
                question = self.__shuffle_options(question)
            return question, combination
        # 題目無效時回傳錯誤題而非 None，避免產生空題目
        logger.warning("LLM 回傳無效題目，改回錯誤提示題")
        return self._build_error_question("LLM 回傳無效題目，請稍後再試。"), combination


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
                    
                    s_name = start_node.get("name", "(unknown)") 
                    e_name = end_node.get("name", "(unknown)") 
                    rel = rel.type
                    text_segments.add(f"{s_name} {rel} {e_name}")

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
