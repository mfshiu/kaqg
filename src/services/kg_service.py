# Required when executed as the main program.
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

from enum import StrEnum, auto
import os
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from knowsys.docker_management import DockerManager
from knowsys.knowledge_graph import KnowledgeGraph



class Topic(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        words = name.split('_')
        formatted_name = ''.join(word.capitalize() for word in words)
        return f"{formatted_name}/KGService/Services"
    
    
    CREATE = auto()
    ACCESS_POINT = auto()
    TRIPLETS_ADD = auto()
    CONCEPTS_QUERY = auto()
    # FACTS_QUERY = auto()
    SECTIONS_QUERY = auto()
    
    
    
    
class KnowledgeGraphService(Agent):

    def __init__(self, cfg):
        app_helper.check_directory_accessible(cfg['kg']['datapath'])

        super().__init__('kg_service.services.wastepro', cfg)
        self.hostname = cfg['kg']['hostname']
        self.datapath = cfg['kg']['datapath']
        logger.info(f"Creating Docker container on host '{self.hostname}'\nwith data storage at '{self.datapath}'")    
    
    
    def on_activate(self):
        try:
            self.docker_manager = DockerManager(self.hostname, self.datapath)
        except Exception as e:
            logger.error(f"Failed to create DockerManager: {e}")
            raise Exception(f"Failed to create DockerManager: {self.hostname}, {self.datapath}")
        self.all_kgs = self.docker_manager.list_KGs()
        logger.info(f"Existing KGs: {self.all_kgs}")

        self.subscribe(Topic.CREATE.value, topic_handler=self.create_knowledge_graph)
        self.subscribe(Topic.ACCESS_POINT.value, topic_handler=self.get_access_point)
        
        self.subscribe(Topic.CONCEPTS_QUERY.value, topic_handler=self.query_concepts)
        # self.subscribe(Topic.FACTS_QUERY.value, topic_handler=self.query_facts)
        self.subscribe(Topic.SECTIONS_QUERY.value, topic_handler=self.query_sections)

        for kg_name in self.all_kgs:
            topic_triplets_add = f'{kg_name}/{Topic.TRIPLETS_ADD.value}'
            self.subscribe(topic_triplets_add, topic_handler=self.handle_triplets_add)
    
    
    def create_knowledge_graph(self, topic:str, pcl:TextParcel):
        kg_name = pcl.content['kg_name']
        http_url, bolt_url = self.docker_manager.create_container(kg_name)

        topic_triplets_add = f'{kg_name}/{Topic.TRIPLETS_ADD.value}'
        self.subscribe(topic_triplets_add, topic_handler=self.handle_triplets_add)

        return {
            'kg_name': kg_name,
            'http_url': http_url,
            'bolt_url': bolt_url,
            'topic_triplets_add': topic_triplets_add,
        }
        
        
    def get_access_point(self, topic:str, pcl:TextParcel):
        logger.debug(f"content: {pcl.content}")
        # pcl.content: {
                # 'kg_name': KG Name,
        #     }
        
        kg_name = pcl.content['kg_name']
        http_url, bolt_url = self.docker_manager.open_KG(kg_name)
        return {
            'http_url': http_url,
            'bolt_url': bolt_url,
        }
        
        
    def handle_triplets_add(self, topic:str, pcl:TextParcel):
        logger.debug(f"content: {pcl.content}")
        # pcl.content: {
                # 'file_id': file_info['file_id'],
                # 'page_number': page_number+1,
                # 'kg_name': kg_name,
                # 'triplets': triplets,
        #     }
        kg_name = pcl.content['kg_name']
        _, bolt_url = self.docker_manager.open_KG(kg_name)
        # _, bolt_url = self.docker_manager.get_urls(kg_name)
        logger.info(f"bolt_url: {bolt_url}")
        with KnowledgeGraph(uri=bolt_url) as kg:
            kg.add_triplets(pcl.content['file_id'], pcl.content['page_number'], pcl.content['triplets'])


    def query_concepts(self, topic:str, pcl:TextParcel):
        logger.debug(f"content: {pcl.content}")
        # pcl.content: {
            # 'kg_name': kg_name,
            # 'document': 'document name',
            # 'section': ['section1', 'section1-1'],
        # }
        kg_name = pcl.content['kg_name']
        _, bolt_url = self.docker_manager.open_KG(kg_name)
        logger.verbose(f"bolt_url: {bolt_url}")
        with KnowledgeGraph(uri=bolt_url) as kg:
            document = kg.query_nodes_by_name(pcl.content['document'], 'document')[0]
            logger.debug(f"document: {document}")
            sections = kg.query_subsections(pcl.content['document'], pcl.content['section'])
            logger.debug(f"sections: {sections}")

            # Use a dictionary to store unique concepts based on their element_id
            unique_concepts = {concept['element_id']: concept for concept in kg.query_nodes_related_by(document['element_id'], 'include_in', 'concept')}
            for section in sections:
                for concept in kg.query_nodes_related_by(section['element_id'], 'include_in', 'concept'):
                    unique_concepts[concept['element_id']] = concept  # Ensures uniqueness
                    
        concepts = list(unique_concepts.values())
        logger.debug(f"concepts: {concepts[:10]}..")

        return {'concepts': concepts}


    def query_facts(self, topic:str, pcl:TextParcel):
        logger.debug(f"content: {pcl.content}")
        # pcl.content: {
                # 'kg_name': kg_name,
                # 'concept': {concept_node},
        #     }
        kg_name = pcl.content['kg_name']
        _, bolt_url = self.docker_manager.open_KG(kg_name)
        logger.verbose(f"bolt_url: {bolt_url}")
        with KnowledgeGraph(uri=bolt_url) as kg:
            concept = pcl.content['concept']
            return {'facts': kg.query_facts(concept['element_id'])}


    def query_sections(self, topic:str, pcl:TextParcel):
        logger.debug(f"content: {pcl.content}")
        # pcl.content: {
                # 'kg_name': kg_name,
                # 'document': 'document name',
                # 'section': 'section name',
        #     }
        data = pcl.content

        _, bolt_url = self.docker_manager.open_KG(data['kg_name'])
        logger.verbose(f"bolt_url: {bolt_url}")
        with KnowledgeGraph(uri=bolt_url) as kg:
            return {'sections': kg.query_subsections(data['document'], data['section'])}


if __name__ == '__main__':
    
    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='validation', agent_config=app_helper.get_agent_config())


        def on_connected(self):
            time.sleep(2)

            self.subscribe(self.agent_id)
            
            pcl = TextParcel({
                'kg': "Test",
                }, topic_return=self.agent_id)
            logger.info(self.M(f"pcl: {pcl}"))
            self.publish('0/' + Topic.TRIPLETS_ADD.value, pcl)


        def on_message(self, topic:str, pcl:TextParcel):
            logger.info(self.M(f"topic: {topic}"))
            logger.info(f"pcl:\n{pcl}")

            self.terminate()
            kg_agent.terminate()


    config = app_helper.get_agent_config()
    config['kg'] = app_helper.config['service']['kg']
    kg_agent = KnowledgeGraphService(config)
    # kg_agent.start_process()
    kg_agent.start_thread()

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
