from abc import ABC, abstractmethod
from typing import List, Any

from agentflow.core.agent import Agent



class NodeRanker(ABC):
    """抽象基類，定義節點排名方法"""
    
    def __init__(self, agent:Agent, subject, document, section):
        self.agent:Agent = agent
        self.subject = subject
        self.document = document
        self.section = section


    @abstractmethod
    def rank_concepts(self, concepts: List[Any]) -> Any:
        """根據排名選擇最佳概念"""
        return concepts[0] if concepts else None


    @abstractmethod
    def rank_facts(self, concept) -> List[Any]:
        """根據排名選擇多個重要事實"""
        return []
    