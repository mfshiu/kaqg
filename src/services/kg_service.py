from ctypes import ArgumentError
from enum import Enum, auto, StrEnum
import hashlib
import mimetypes
import os
import random
import time
import uuid
from xml.sax import handler

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel
import knowsys

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))



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
    
    
    @staticmethod
    def get_topic(action:Action, kg_id):
        if action == Action.TRIPLETS_ADD:
            topic = f'{kg_id}/{Topic.TOPIC_TRIPLETS_ADD.value}'
        else:
            raise ValueError(f"Invalid action: {action}")
        
        return topic
    
    
    def __init__(self, cfg):
        super().__init__('kg_service.services.wastepro', cfg)


    def on_connected(self):
        self._subscribe(Topic.TOPIC_CREATE.value, topic_handler=self.handle_create)
        self._subscribe(Topic.TOPIC_CONCEPTS_QUERY.value, topic_handler=self.query_concepts)
        self._subscribe(Topic.TOPIC_FACTS_QUERY.value, topic_handler=self.query_facts)
        self._subscribe(KnowledgeGraphService.TOPIC_QUERY_SECTIONS, topic_handler=self.query_sections)


    def handle_create(self, topic:str, pcl:TextParcel):
        kg_id = 0
        topic_triplets_add = KnowledgeGraphService.get_topic('triplets_add', kg_id)
        # Create KG
        self._subscribe(topic_triplets_add, topic_handler=self.handle_triplets_add)
        
        return {
            'kg_id': kg_id,
            'topic_triplets_add': topic_triplets_add,
        }


    def query_concepts(self, topic:str, pcl:TextParcel):
        pass


    def query_facts(self, topic:str, pcl:TextParcel):
        pass


    def query_sections(self, topic:str, pcl:TextParcel):
        conditions:dict = pcl.content
        kg = knowsys.get_knowledge_graph(conditions['kg_id'])
        
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
        
        
    def handle_triplets_add(self, topic:str, pcl:TextParcel):
        logger.info(f"content: {pcl.content}")
        # pcl.content: {
        #         'source_type': 'pdf',
        #         'file_id': file_info['file_id'],
        #         'page_number': page_number,
        #         'triplets': triplets,
        #         'kg_id': kg_info['kg_id'],
        #     }
