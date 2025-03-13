import random
from typing import List, Any

from agentflow.core.parcel import TextParcel
from generation.ranker.node_ranker import NodeRanker
from knowsys.knowledge_graph import KnowledgeGraph
from services.kg_service import Topic


import logging, os
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))



class SimpleRanker(NodeRanker):
    """基本排名器，隨機選擇一個概念與最多 5 個事實"""
    
    def __init__(self, agent, subject, document, section):
        super().__init__(agent, subject, document, section)


    def rank_concepts(self, concepts: List[Any]) -> Any:
        return random.choice(concepts) if concepts else None


    def rank_facts(self, concept) -> List[Any]:
        pcl = TextParcel({'kg_name': self.subject})
        bolt_url = self.agent.publish_sync(Topic.ACCESS_POINT.value, pcl).content['bolt_url']
        with KnowledgeGraph(uri=bolt_url) as kg:
            facts = kg.query_nodes_related_by(concept['element_id'], 'is_a', 'fact')
        
        return random.sample(facts, min(5, len(facts))) if facts else []
