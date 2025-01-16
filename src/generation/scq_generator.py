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
    
    
    def generate_question(self, source_sentences, difficulty):
        # difficulty: 30, 50, 70
        # 丙：10分 for difficulty 30
        # 乙：14分 for difficulty 50
        # 甲：18分 for difficulty 70
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
