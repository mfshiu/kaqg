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
logger:Logger = __import__('src').get_logger()


class KnowledgeGraphService(Agent):
    TOPIC_TRIPLETS_ADD = "AddTriplets/KGService/Services"
    TOPIC_CREATE = "Create/KGService/Services"
    
    
    def __init__(self, cfg):
        super().__init__('kg_service.services.wastepro', cfg)


    def on_connected(self):
        self._subscribe(KnowledgeGraphService.TOPIC_CREATE, topic_handler=self.handle_create)


    def handle_create(self, topic:str, pcl:TextParcel):
        kg_id = 0
        topic_triplets_add = f'{kg_id}/{KnowledgeGraphService.TOPIC_TRIPLETS_ADD}'
        # Create KG
        self._subscribe(topic_triplets_add, topic_handler=self.handle_triplets_add)
        
        return {
            'kg_id': kg_id,
            'topic_triplets_add': topic_triplets_add,
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
