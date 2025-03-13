from neo4j import GraphDatabase
from knowsys.knowledge_graph import KnowledgeGraph
from knowsys import docker_management
import random

class KG_console:
    url = ""
    uri = ""

    def __init__(self, uri) -> None:
        manager = docker_management.DockerManager()
        self.driver = GraphDatabase.driver(uri)
    
    
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
                
                

#變數調整，由指定section中抽取一個concept，並獲取由連接數目排序的facts
KG_name = "Wastepro02"
section_name = "壹、前言"
search_depth = 2  # 搜尋的層數
#retrieve fact and sort
outgoing_weight = 1
incoming_weight = 1



manager = docker_management.DockerManager()
url,uri = manager.open_KG(KG_name)
KG = KG_console(uri)


#知識圖譜裡沒有section tag,暫時將"MATCH (s:section"替換成MATCH (s:structure
section_querys = f"""
MATCH (s:structure {{name:'{section_name}'}}) RETURN s;
"""

sorted_nodes = []

for cypher in section_querys.splitlines():
    if cypher.strip() != "":
        query_results, summary, keys = KG.query(cypher.strip())
        for query_result in query_results:
            record = query_result[keys[0]]
            print(record.get('name'))
            # 使用 sector_node 進行後續查詢
            concept_query = f"MATCH (s)<-[:include_in]-(c:concept) WHERE s.name = '{record.get('name')}' RETURN c" #使用f-string來將變數放入query中，並且使用id()來比對節點
            concept_result , summary, keys= KG.query(concept_query)
            concept = []
            if concept_result:
                print("Concept found : ")
                for concept_record in concept_result:
                    concept.append(concept_record[keys[0]])
                    print(concept_record[keys[0]].get("name"),end=", ")
                
                random.seed()
                selected_concept = random.choice(concept)
                print("\nselected one : ",selected_concept.get("name"))
                
                start_node_name = selected_concept.get("name")  # 起始節點的名稱
                
                for i in range(search_depth):
                    fact_query_test3=f"""
                    MATCH (start_node {{name: '{start_node_name}'}})-[r*{i+1}..{i+1}]-(related_node)
                    WHERE ALL(rel IN r WHERE type(rel) <> 'include_in')
                    WITH DISTINCT related_node
                    RETURN related_node,
                        size([(related_node)-->(x) | x IN []]) AS outgoing_degree,
                        size([(related_node)<--(x) | x IN []]) AS incoming_degree
                    ORDER BY (outgoing_degree*{outgoing_weight} + incoming_degree*{incoming_weight}) DESC"""
                    
                    
                    facts , summary, keys= KG.query(fact_query_test3)
                    


                    for fact in facts:
                        node_name = fact[keys[0]].get("name")
                        out_count = fact[keys[1]]
                        in_count = fact[keys[2]]
                        
                        sorted_nodes.append((node_name,in_count,out_count))

                # print("Sorted nodes by relationship count:")
                # for node,in_count,out_count in sorted_nodes:
                #     print(f"{node} in count: {in_count} out count:{out_count}")
                    
                
            else:
                print(f"找不到與{section_name}相關的Concept")
print("facts found：\n",sorted_nodes)