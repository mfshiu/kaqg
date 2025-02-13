# Required when executed as the main program.
import os, sys

from knowsys.knowledge_graph import KnowledgeGraph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from enum import Enum, auto, StrEnum
import os
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel
import knowsys

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from knowsys.docker_management import DockerManager


class Action(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()

    TRIPLETS_ADD = auto()
    CREATE = auto()
    QUERY_CONCEPTS = auto()
    QUERY_FACTS = auto()
    QUERY_SECTIONS = auto()



class Topic(StrEnum):
    TOPIC_CREATE = "Create/KGService/Services"
    TOPIC_TRIPLETS_ADD = "AddTriplets/KGService/Services"
    TOPIC_CONCEPTS_QUERY = "QueryConcepts/KGService/Services"
    TOPIC_FACTS_QUERY = "QueryFacts/KGService/Services"
    TOPIC_SECTIONS_QUERY = "QuerySections/KGService/Services"
    
    
    
class KnowledgeGraphService(Agent):

    def __init__(self, cfg):
        super().__init__('kg_service.services.wastepro', cfg)
        self.hostname = cfg['kg']['hostname']
        self.datapath = cfg['kg']['datapath']
        logger.info(f"Creating Docker container on host '{self.hostname}'\nwith data storage at '{self.datapath}'")    


    @staticmethod
    def get_topic(action:Action, kg_name):
        if action == Action.TRIPLETS_ADD:
            topic = f'{kg_name}/{Topic.TOPIC_TRIPLETS_ADD.value}'
        else:
            raise ValueError(f"Invalid action: {action}")
        
        return topic
    
    
    def on_activate(self):
        self.docker_manager = DockerManager(self.hostname, self.datapath)
        self.all_kgs = self.docker_manager.list_KGs()
        logger.info(f"Existing KGs: {self.all_kgs}")

        self._subscribe(Topic.TOPIC_CREATE.value, topic_handler=self.create_knowledge_graph)
        self._subscribe(Topic.TOPIC_CONCEPTS_QUERY.value, topic_handler=self.query_concepts)
        self._subscribe(Topic.TOPIC_FACTS_QUERY.value, topic_handler=self.query_facts)
        self._subscribe(Topic.TOPIC_SECTIONS_QUERY, topic_handler=self.query_sections)

        for kg_name in self.all_kgs:        
            topic_triplets_add = KnowledgeGraphService.get_topic(Action.TRIPLETS_ADD, kg_name)
            self._subscribe(topic_triplets_add, topic_handler=self.handle_triplets_add)
    
    
    def create_knowledge_graph(self, topic:str, pcl:TextParcel):
        kg_name = pcl.content['kg_name']
        http_url, bolt_url = self.docker_manager.create_container(kg_name)

        topic_triplets_add = KnowledgeGraphService.get_topic(Action.TRIPLETS_ADD, kg_name)
        self._subscribe(topic_triplets_add, topic_handler=self.handle_triplets_add)

        return {
            'kg_name': kg_name,
            'http_url': http_url,
            'bolt_url': bolt_url,
            'topic_triplets_add': topic_triplets_add,
        }
        
        
    def handle_triplets_add(self, topic:str, pcl:TextParcel):
        logger.debug(f"content: {pcl.content}")
        # pcl.content: {
                # 'source_type': 'pdf',
                # 'file_id': file_info['file_id'],
                # 'page_number': page_number+1,
                # 'kg_name': kg_name,
                # 'triplets': triplets,
        #     }
        kg_name = pcl.content['kg_name']
        _, bolt_url = self.docker_manager.open_KG(kg_name)
        # _, bolt_url = self.docker_manager.get_urls(kg_name)
        logger.info(f"bolt_url: {bolt_url}")
        kg = KnowledgeGraph(uri=bolt_url, auth=('neo4j', '!Qazxsw2'))
        data = pcl.content
        kg.add_triplets(data['source_type'], data['file_id'], data['page_number'], data['triplets'])
        

    def query_concepts(self, topic:str, pcl:TextParcel):
        pass


    def query_facts(self, topic:str, pcl:TextParcel):
        pass


    def query_sections(self, topic:str, pcl:TextParcel):
        conditions:dict = pcl.content
        kg = knowsys.get_knowledge_graph(conditions['kg_name'])
        
        query_result = kg.query("MATCH (n:Structure) RETURN id(n) AS id, n.name AS name")
        nodes = {record['id']: {'name': record.get('name', None)} for record in query_result}
        
        query_result = kg.query("""MATCH (a:Structure)-[r]->(b:Structure) RETURN 
                                id(r) AS id, 
                                type(r) AS type, 
                                id(a) AS start_node, 
                                id(b) AS end_node""")
        relationships = [
            {
                'id': record['id'],
                'type': record['type'],
                'start_node': record['start_node'],
                'end_node': record['end_node']
            }
            for record in query_result
        ]
        
        return {
            'nodes': nodes,  # Index nodes by ID for fast lookup
            'relationships': relationships
        }


if __name__ == '__main__':
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='validation', agent_config=app_helper.get_agent_config())


        def on_connected(self):
            time.sleep(2)

            self._subscribe(self.agent_id)
            
            pcl = TextParcel({
                'kg': "Test",
                }, topic_return=self.agent_id)
            logger.info(self.M(f"pcl: {pcl}"))
            self._publish('0/' + Topic.TOPIC_TRIPLETS_ADD.value, pcl)


        def on_message(self, topic:str, pcl:TextParcel):
            logger.info(self.M(f"topic: {topic}"))
            logger.info(f"pcl:\n{pcl}")

            self.terminate()
            kg_agent.terminate()


    from services.llm_service import LlmService
    
    config = app_helper.get_agent_config()
    config['kg'] = app_helper.config['service']['kg']
    kg_agent = KnowledgeGraphService(config)
    kg_agent.start_process()

    if "-test" in sys.argv:
        ValidationAgent().start_thread()

    app_helper.wait_agent(kg_agent)

    # config = app_helper.get_agent_config()
    # config['kg'] = app_helper.config['service']['kg']
    # kg_agent = KnowledgeGraphService(config)
    # kg_agent.start_process()
    # # main_agent.start_thread()

    # if "-test" in sys.argv:
    #     ValidationAgent().start_thread()

    # app_helper.wait_agent(kg_agent)
