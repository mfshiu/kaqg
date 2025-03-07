from abc import ABC, abstractmethod
from typing import List, Any



class NodeRanker(ABC):
    """抽象基類，定義節點排名方法"""

    @abstractmethod
    def rank_concepts(self, concepts: List[Any]) -> Any:
        """根據排名選擇最佳概念"""
        pass

    @abstractmethod
    def rank_facts(self, facts: List[Any]) -> List[Any]:
        """根據排名選擇多個重要事實"""
        pass
    