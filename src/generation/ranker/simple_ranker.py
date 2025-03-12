from typing import List, Any

from generation.ranker.node_ranker import NodeRanker



class SimpleRanker(NodeRanker):
    """基本排名器，選擇第一個概念與前兩個事實"""

    def rank_concepts(self, concepts: List[Any]) -> Any:
        return concepts[0] if concepts else None

    def rank_facts(self, facts: List[Any]) -> List[Any]:
        return facts[:2] if facts else []
