from typing import List, Any

from generation.ranker.node_ranker import NodeRanker



class WeightedRanker(NodeRanker):
    """智慧排名器，根據評分選擇最佳概念與前幾個高分事實"""
    
    def __init__(self, subject, document, section):
        super().__init__(subject, document, section)
        

    def rank_concepts(self, concepts: List[Any]) -> Any:
        return max(concepts, key=lambda x: x.get("score", 0)) if concepts else None
    

    def rank_facts(self, concept) -> List[Any]:
        return sorted(facts, key=lambda x: x.get("score", 0), reverse=True)[:3] if facts else []
