from neo4j import GraphDatabase
from knowsys import docker_management
import random

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
        query_result, summary, keys = self.driver.execute_query(query_statement)
            
        return query_result, summary, keys
    
    def query_result_parser(query_ressults,keys,target_properties):
        """
        單一key時使用
        """
        result=[]
        for query_ressult in query_ressults:
            for property in target_properties:
                result.append(query_ressult[keys[0]].get(property))
    
if __name__ == '__main__':
    manager = docker_management.DockerManager()
    KG_name = "Sector"
    # manager.delete_KG(KG_name)
    KG = KnowledgeGraph(KG_name)
    
    #sector search 
    sector_name = "S"
    sector_querys = f"""
MATCH (s:Sector {{name:'{sector_name}'}}) RETURN s;
 """
    for cypher in sector_querys.splitlines():
        if cypher.strip() != "":
            query_results, summary, keys = KG.query(cypher.strip())
            for query_result in query_results:
                record = query_result[keys[0]]
                print(record.get('name'))
                # 使用 sector_node 進行後續查詢
                concept_query = f"MATCH (s)-[:include_in]->(c:Concept) WHERE s.name = '{record.get('name')}' RETURN c" #使用f-string來將變數放入query中，並且使用id()來比對節點
                concept_result , summary, keys= KG.query(concept_query)
                concept = []
                if concept_result:
                    for concept_record in concept_result:
                        concept.append(concept_record[keys[0]])
                        print("Concept found : ",concept_record[keys[0]].get("name"))
                    
                    random.seed()
                    selected_concept = random.choice(concept)
                    print("selected one : ",selected_concept.get("name"))
                    
                    
                    
                    
                    #old cypher
                    start_node_name = selected_concept.get("name")  # 起始節點的名稱
                    search_depth = 2  # 搜尋的層數
                    fact_query = f"""
                    MATCH (start_node {{name: '{start_node_name}'}})-[r*{search_depth}..{search_depth}]-(related_node)
                    WHERE ALL(rel IN r WHERE type(rel) <> 'include_in')
                    RETURN DISTINCT related_node
                    """
                    fact_query_test = f"""
                    MATCH (start_node {{name: '{start_node_name}'}})-[r*{search_depth}..{search_depth}]-(related_node)
                    WHERE ALL(rel IN r WHERE type(rel) <> 'include_in')
                    WITH DISTINCT related_node
                    MATCH (related_node)-[all_rel]-()
                    RETURN related_node, COUNT(all_rel) AS degree
                    ORDER BY degree DESC
                    """
                    
                    
                    
                    
                    #retrieve fact and sort
                    outgoing_weight = 1
                    incoming_weight = 1
                    
                    fact_query_test3=f"""
                    MATCH (start_node {{name: '{start_node_name}'}})-[r*{search_depth}..{search_depth}]-(related_node)
WHERE ALL(rel IN r WHERE type(rel) <> 'include_in')
WITH DISTINCT related_node
RETURN related_node,
       size([(related_node)-->(x) | x IN []]) AS outgoing_degree,
       size([(related_node)<--(x) | x IN []]) AS incoming_degree
ORDER BY (outgoing_degree*{outgoing_weight} + incoming_degree*{incoming_weight}) DESC"""
                    
                    
                    facts , summary, keys= KG.query(fact_query_test3)
                    
                    # facts, summary, keys = KG.query(fact_query)

                    sorted_nodes = []

                    for fact in facts:
                        node_name = fact[keys[0]].get("name")
                        out_count = fact[keys[1]]
                        in_count = fact[keys[2]]
                        
                        sorted_nodes.append((node_name,in_count,out_count))

                    print("Sorted nodes by relationship count:")
                    for node,in_count,out_count in sorted_nodes:
                        print(f"{node} in count: {in_count} out count:{out_count}")
                        
                                        
                        
                    # facts , summary, keys= KG.query(fact_query_test)
                    
                    # # facts, summary, keys = KG.query(fact_query)

                    # sorted_nodes = []

                    # for fact in facts:
                    #     node_name = fact[keys[0]].get("name")
                    #     relationship_count = fact[keys[1]]
                    #     sorted_nodes.append((node_name, relationship_count))

                    # print("Sorted nodes by relationship count:")
                    # for node, count in sorted_nodes:
                    #     print(f"{node}: {count}")
                    
                else:
                    print(f"找不到與{sector_name}相關的Concept")

