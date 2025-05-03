from neo4j import GraphDatabase
from knowsys.knowledge_graph import KnowledgeGraph
from knowsys import docker_management
import random

class FactRetriever:
    url = ""
    uri = ""

    def __init__(self, uri) -> None:
        manager = docker_management.DockerManager()
        self.driver = GraphDatabase.driver(uri)
    
    
    def query(self, query_statement):
        query_result, summary, keys = self.driver.execute_query(query_statement)
            
        return query_result, summary, keys
                
    def fact_query(self,start_node_name,depth,sample=0,incoming_weight = 1,outgoing_weight = 1):
        fact_query=f"""
        MATCH (start_node {{name: '{start_node_name}'}})-[r*{depth+1}..{depth+1}]-(related_node)
        WHERE ALL(rel IN r WHERE type(rel) <> 'include_in')
        WITH DISTINCT related_node
        RETURN related_node,
            size([(related_node)-->(x) | x IN []]) AS outgoing_degree,
            size([(related_node)<--(x) | x IN []]) AS incoming_degree
        ORDER BY (outgoing_degree*{outgoing_weight} + incoming_degree*{incoming_weight}) DESC"""
        facts , summary, keys=self.query(fact_query)
        
        
        return facts, summary, keys
    
    def retrieve_sorted_facts(self,section_name,search_depth,target_attributes = ["name"],sample=0,incoming_weight = 1,outgoing_weight = 1):
        """
        舊的retrieve facts方法，僅透過fact節點的連入連出關係進行計算。
        """
        #知識圖譜裡沒有section tag,暫時將"MATCH (s:section"替換成MATCH (s:structure
        section_querys = f"""MATCH (s:structure {{name:'{section_name}'}}) RETURN s;"""
        sorted_nodes = []

        query_results, summary, keys = fact_retriever.query(section_querys.strip())
        for query_result in query_results:
            record = query_result[keys[0]]
            print(record.get('name'))
            # 使用 sector_node 進行後續查詢
            concept_query = f"MATCH (s)<-[:include_in]-(c:concept) WHERE s.name = '{record.get('name')}' RETURN c" #使用f-string來將變數放入query中，並且使用id()來比對節點
            concept_result , summary, keys= fact_retriever.query(concept_query)
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
                
                #sample實作中，問題是sample後深度搜尋方式
                if sample:
                    facts , summary, keys= fact_retriever.fact_query(start_node_name,0,incoming_weight,outgoing_weight)#搜尋最相鄰一層
                    facts = random.sample(facts, sample)
                else:
                    for depth in range(search_depth):
                        facts , summary, keys= fact_retriever.fact_query(start_node_name,depth,incoming_weight,outgoing_weight)#依重要度與深度排序
                    
                    
                for fact in facts:
                    info=[]
                    for attr in target_attributes:
                        info.append(fact[keys[0]].get(attr))

                    sorted_nodes.append(info)

            else:
                print(f"找不到與{section_name}相關的Concept")
        return sorted_nodes
    
    def pagerank_query(self, target_node_elementId, depth,target_attributes = ["name"], max_iterations=20, damping_factor=0.85):
        """
        取得與指定目標節點相連的節點，並依 PageRank 分數排序回傳
        :param target_node_name: 目標節點名稱
        :param max_iterations: PageRank 演算法最大迭代次數
        :param damping_factor: PageRank 阻尼係數
        :return: 依 PageRank 排序的相鄰節點列表 (名稱, PageRank 分數)
        """
        
        check_graph_query = """
        CALL gds.graph.exists('myGraph') YIELD exists
        RETURN exists;
        """
        results, _, _ = self.query(check_graph_query)
        graph_exists = results[0]["exists"] if results else False
        
        if not graph_exists:
            # 1. **先建立 GDS 圖**
            create_graph_query = """
            CALL gds.graph.project(
                'myGraph',
                '*',  // 所有節點
                {
                    all: {
                        type: '*',
                        orientation: 'NATURAL'
                    }
                }
            );
            """
            self.query(create_graph_query)

        pagerank_query = f"""
        CALL gds.pageRank.stream('myGraph', {{ maxIterations: {max_iterations}, dampingFactor: {damping_factor}}})
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS n, score
        MATCH (n)-[r*1..{depth}]-(target:concept) 
        WHERE elementId(target) = '{target_node_elementId}'
        WITH n, score, r
        WHERE ALL(rel IN r WHERE type(rel) <> 'include_in')
        RETURN n AS related_nodes, score
        ORDER BY score DESC;
        """
        results, summary, keys = self.query(pagerank_query)
        
        # 3. **轉換結果**
        sorted_nodes = []
        last_id  = None
        for record in results:
            if record['related_nodes'].element_id==last_id:
                continue
            last_id = record['related_nodes'].element_id
            info=[]
            for attr in target_attributes:
                info.append(record[keys[0]].get(attr))
            info.append(record["score"])
            sorted_nodes.append(info)

        return sorted_nodes

       

KG_name = "Wastepro02"
manager = docker_management.DockerManager()
manager.create_container(KG_name)
url,uri = manager.open_KG(KG_name)

fact_retriever = FactRetriever(uri)


target_node_element_id = "4:5cf13260-6b9a-4d94-bf90-9424b4ac6b3d:876" # 目標concept(環境正義)的ElementID
target_attributes = ["name","file_id","page_number"]
search_depth = 2  # 搜尋的層數

page_rank_node = fact_retriever.pagerank_query(target_node_element_id,search_depth,target_attributes)
print(page_rank_node)

