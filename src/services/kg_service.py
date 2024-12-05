import hashlib
import mimetypes
import os
import random
import time
import uuid
from xml.sax import handler

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel

from logging import Logger

import knowsys
logger:Logger = __import__('src').get_logger()


class KnowledgeGraphService(Agent):
    TOPIC_TRIPLETS_ADD = "AddTriplets/KGService/Services"
    TOPIC_CREATE = "Create/KGService/Services"
    TOPIC_QUERY_CONCEPTS = "QueryConcepts/KGService/Services"
    TOPIC_QUERY_FACTS = "QueryFacts/KGService/Services"
    TOPIC_QUERY_SECTIONS = "QuerySections/KGService/Services"
    
    
    def __init__(self, cfg):
        super().__init__('kg_service.services.wastepro', cfg)


    def on_connected(self):
        self._subscribe(KnowledgeGraphService.TOPIC_CREATE, topic_handler=self.handle_create)
        self._subscribe(KnowledgeGraphService.TOPIC_QUERY_CONCEPTS, topic_handler=self.query_concepts)
        self._subscribe(KnowledgeGraphService.TOPIC_QUERY_FACTS, topic_handler=self.query_facts)
        self._subscribe(KnowledgeGraphService.TOPIC_QUERY_SECTIONS, topic_handler=self.query_sections)


    def handle_create(self, topic:str, pcl:TextParcel):
        kg_id = 0
        topic_triplets_add = f'{kg_id}/{KnowledgeGraphService.TOPIC_TRIPLETS_ADD}'
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
        nodes_result = kg.query("MATCH (n) RETURN id(n) AS id, n.name AS name")
        nodes = {record['id']: {'name': record.get('name', None)} for record in nodes_result}
        
        relationships_result = kg.query("""MATCH (a)-[r]->(b) RETURN 
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
            for record in relationships_result
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
