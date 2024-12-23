from knowsys.knowledge_graph import KnowledgeGraph


def create_knowledge_graph(name:str) -> KnowledgeGraph:
    return KnowledgeGraph(0)


def get_knowledge_graph(id) -> KnowledgeGraph:
    return KnowledgeGraph(id)
