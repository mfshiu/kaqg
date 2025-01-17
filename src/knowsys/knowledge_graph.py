from neo4j import GraphDatabase

from knowsys import docker_management


class KnowledgeGraph:
    url = ""
    uri = ""
    #username = "neo4j"
    #password = "12345678"

    def __init__(self, id) -> None:
        self.id = id
        self.name = id
        manager = docker_management.DockerManager()
        self.url,self.uri = manager.open_KG(id)
        self.driver = GraphDatabase.driver(self.uri)
    
    
    def query(self, query_statement):
        with self.driver.session() as session:
            query_result = session.run(query_statement)
            
        return query_result
    
    
if __name__ == '__main__':
    KG = KnowledgeGraph("test_KG")
    test_querys = """
            CREATE (:Technology {name: 'SURGE', alias: 'SURGE, 特別是對比學習版本'});
            CREATE (:Technology {name: 'Baselines', alias: 'Baselines, 基準'});
            CREATE (:Technology {name: 'Retrieval Variants', alias: 'Retrieval Variants, 檢索變體'});
            CREATE (:Theory {name: '知識檢索', alias: '知識檢索'});
            CREATE (:Theory {name: '問答生成', alias: '問答生成'});
            MATCH (a {name: 'SURGE'}), (b {name: 'Baselines'}) CREATE (a)-[:outperform]->(b);
            MATCH (a {name: '對比學習'}), (b {name: '知識檢索'}) CREATE (a)-[:is_effective_in]->(b);
            MATCH (a {name: '對比學習'}), (b {name: '問答生成'}) CREATE (a)-[:is_effective_in]->(b);
            """
    for cypher in test_querys.splitlines():
        if cypher.strip() != "":
            KG.query(cypher.strip())

