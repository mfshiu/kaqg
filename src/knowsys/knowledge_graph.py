from neo4j import GraphDatabase



class KnowledgeGraph:
    uri = "bolt://localhost:7687"
    username = "neo4j"
    password = "12345678"
    

    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(KnowledgeGraph.uri, auth=(KnowledgeGraph.username, KnowledgeGraph.password))
    
    
    def query(self, query_statement):
        with self.driver.session() as session:
            query_result = session.run(query_statement)
            
        return query_result
        