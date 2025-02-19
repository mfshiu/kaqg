import random
import signal
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel, Parcel
import app_helper
from services.file_service import FileService
from services.kg_service import KnowledgeGraphService


from logging import Logger
logger:Logger = __import__('wastepro').get_logger()



class SingleChoiceGenerator(Agent):
    TOPIC_CREATE = "Create/SCQ/Generation"


    def __init__(self, config:dict):
        logger.info(f"config: {config}")
        super().__init__(name='scq.generation.wp', agent_config=config)


    def on_connected(self):
        logger.debug(f"on_connected")
        self._subscribe(SingleChoiceGenerator.TOPIC_CREATE, topic_handler=self._handle_create)


    def _handle_create(self, topic, pcl:TextParcel):
        question_criteria = pcl.content
        # question_criteria = {
        #     'question_id': 'Q101',              # 使用者自訂題目 ID
        #     'section': ['chapter1', 'ch1-1'],   # 指定章節
        #     'difficulty': 50,                   # 難度 30, 50, 70
        # }
        
        generated_question = self._create_question(question_criteria)

        logger.debug(f"generated_question: {generated_question}")
        return generated_question


    def _create_question(self, question_criteria):
        # Retrieve target concept
        concept_nodes = self.retrieve_concept_nodes(question_criteria['section'])
        if not concept_nodes:
            raise ValueError("Unable to generate any questions from the question criteria.")
        target_concept = self.choice_concept(concept_nodes)

        # Retrieve fact nodes
        fact_nodes = self.retrieve_fact_nodes(target_concept) # Must be sorted.
        if not fact_nodes:
            raise ValueError(f"Unable to generate any questions from the concept: {target_concept}")

        # From fact nodes to question
        source_sentences = self.generate_source_sentences(fact_nodes)

        question = self.generate_question(source_sentences, question_criteria['difficulty'])
        question['question_criteria'] = question_criteria

        return question

    
    def choice_concept(self, concept_nodes):
        return random.choice(concept_nodes)
    
    def _get_one_weighted_combination(self,S):
        """
        隨機取得一組符合條件的 7 個參數組合，考慮各參數的權重。
        每個參數的分數為 1, 2, 3，且加權總和需落在 S ± 1 的範圍內。

        權重分配：
        - stem_cognitive_level：1.5
        - high_distractor_count：1.2
        - 其他特徵：1

        :param S: 目標總分
        :return: 一組符合條件的參數組合，對應七個具體描述
        """
        # 定義各參數的權重  
        weights = [1, 1, 1.5, 1, 1, 1, 1.2]
        
        # 篩選符合條件的組合
        valid_combinations = []
        for combination in product(range(1, 4), repeat=7):
            weighted_sum = sum(x * w for x, w in zip(combination, weights))
            if S - 1 <= weighted_sum <= S + 1:
                valid_combinations.append(combination)
        
        # 若無符合條件的組合，返回 None
        if not valid_combinations:
            return None

        # 隨機選取一組並命名參數
        selected = random.choice(valid_combinations)
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
        # 定義參數範圍對應描述
        stem_length_desc = {
            "high": "題幹字數較長（超過 20 字）",
            "medium": "題幹字數中等（15 至 35 字之間）",
            "low": "題幹字數較短（10 至 25 字）"
        }

        technical_term_density_desc = {
            "high": "題幹使用了較多專業術語（3 個以上）",
            "medium": "題幹有適當的專業術語（2 至 4 個）",
            "low": "題幹使用較少或無專業術語（0 至 2 個）"
        }

        cognitive_level_desc = {
            "high": "需進行分析、綜合或評估",
            "medium": "涉及知識點的理解與綜合",
            "low": "僅需記憶知識點"
        }

        option_length_desc = {
            "high": "選項文字較長（5 字以上）",
            "medium": "選項文字中等（3 至 8 字之間）",
            "low": "選項文字較短（1 至 5 字）"
        }

        option_similarity_desc = {
            "high": "選項間有較高相似度（60% 以上）",
            "medium": "選項間相似度適中（45% 左右）",
            "low": "選項間相似度較低（30% 以下）"
        }

        stem_option_similarity_desc = {
            "high": "題幹與選項內容高度相關（60% 以上）",
            "medium": "題幹與選項內容相關性適中（45% 左右）",
            "low": "題幹與選項內容相關性較低（30% 以下）"
        }

        high_distractor_count_desc = {
            "high": "包含 3 個以上的高誘答選項",
            "medium": "包含 2 個高誘答選項",
            "low": "包含 1 個高誘答選項"
        }

        # 根據參數生成對應敘述
        prompt = (
            f"題幹字數：{stem_length_desc['high' if parameters['stem_length'] == 3 else 'medium' if parameters['stem_length'] == 2 else 'low']}；\n"
            f"題幹專業詞密度：{technical_term_density_desc['high' if parameters['stem_technical_term_density'] == 3 else 'medium' if parameters['stem_technical_term_density'] == 2 else 'low']}；\n"
            f"認知程度：{cognitive_level_desc['high' if parameters['stem_cognitive_level'] == 3 else 'medium' if parameters['stem_cognitive_level'] == 2 else 'low']}；\n"
            f"選項平均字數：{option_length_desc['high' if parameters['option_average_length'] == 3 else 'medium' if parameters['option_average_length'] == 2 else 'low']}；\n"
            f"選項間相似度：{option_similarity_desc['high' if parameters['option_similarity'] == 3 else 'medium' if parameters['option_similarity'] == 2 else 'low']}；\n"
            f"題幹與選項相似度：{stem_option_similarity_desc['high' if parameters['stem_option_similarity'] == 3 else 'medium' if parameters['stem_option_similarity'] == 2 else 'low']}；\n"
            f"高誘答選項數：{high_distractor_count_desc['high' if parameters['high_distractor_count'] == 3 else 'medium' if parameters['high_distractor_count'] == 2 else 'low']}。"
        )
        return prompt    

    def generate_question(self, source_sentences, difficulty):
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
        combination = self._get_one_weighted_combination(score)
        prompt = self._generate_prompt(combination)
        
        # 生成題目
        queation = {
            'type': 'SCQ',
            'stem': 'The question stem',
            'options': ['option1', 'option2', 'option3', 'option4'],
            'answer': 1,
            # 'question_criteria': question_criteria
        }
        return queation
    
    
    def generate_source_sentences(self, fact_nodes):
        return [
            "104 年全國各縣市焚化底渣產量約占焚化量之 15%",
            "104 年度一般廢棄物底渣再利用量占該年度底渣總量之89.3%",
            "基隆市、臺北市、新北市、桃園市、新竹市、苗栗縣、臺中市、彰化縣、嘉義市、嘉義縣、臺南市、高雄市、屏東縣等，已將所轄焚化廠底渣委外再利用"
        ]
    
    
    def retrieve_concept_nodes(self, section):
        if 'chapter1' == section[0]:
            return ['廢棄物']
        else:
            return None
    
    
    def retrieve_fact_nodes(self, concept):
        facts = {
            "年份": ["104 年"],
            "百分比": ["15%", "89.3%"],
            "政府機構": ["環境部"],
            "城市": [
                "基隆市", "臺北市", "新北市", "桃園市", "新竹市",
                "臺中市", "嘉義市", "臺南市", "高雄市"
            ],
            "縣": ["苗栗縣", "彰化縣", "嘉義縣", "屏東縣"],
            "廢棄物": ["焚化底渣", "一般廢棄物", "底渣"],
            "設施": ["掩埋場", "焚化廠"],
            "廢棄物管理": ["資源回收再利用"],
            "建材": ["營建替代級配材料"],
            "廢棄物處理": ["分選", "再利用", "掩埋", "最終處置"]
        }
        return facts.get(concept, [])
            


if __name__ == '__main__':
    main_agent = SingleChoiceGenerator(app_helper.get_agent_config())
    logger.debug(f'***** {main_agent.__class__.__name__} *****')
    

    def signal_handler(signal, frame):
        main_agent.terminate()
    signal.signal(signal.SIGINT, signal_handler)


    main_agent.start_process()

    time.sleep(1)
    while main_agent.is_active():
        print('.', end='')
        time.sleep(1)
