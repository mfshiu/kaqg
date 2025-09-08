from typing import List, Any
from generation.ranker.node_ranker import NodeRanker
from neo4j import GraphDatabase
import networkx as nx
from collections import defaultdict
import math
import numpy as np
import random

class ConceptScorer:
    def __init__(self, uri="bolt://localhost:7688", username="neo4j", password=""):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.graph = None
        self.pagerank_scores = None

    def connect(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))

    def disconnect(self):
        if self.driver:
            self.driver.close()

    def build_graph(self):
        self.graph = nx.DiGraph()
        with self.driver.session() as session:
            # facts 與 concepts
            result = session.run("""
                MATCH (f)-[:is_a]->(c)
                RETURN f.name AS fact_name, c.name AS concept_name
            """)
            for record in result:
                fact = record["fact_name"]
                concept = record["concept_name"]
                if fact and concept:
                    self.graph.add_edge(fact, concept)
            # concepts 與 structures
            result = session.run("""
                MATCH (c)-[:include_in]->(s)
                RETURN c.name AS concept_name, s.name AS structure_name
            """)
            for record in result:
                concept = record["concept_name"]
                structure = record["structure_name"]
                if concept and structure:
                    self.graph.add_edge(concept, structure)
            # facts 與 facts
            result = session.run("""
                MATCH (f1:fact)-[r]->(f2:fact)
                RETURN f1.name AS fact1_name, f2.name AS fact2_name
            """)
            for record in result:
                fact1 = record["fact1_name"]
                fact2 = record["fact2_name"]
                if fact1 and fact2:
                    self.graph.add_edge(fact1, fact2)

    def calculate_pagerank(self):
        if self.graph is None:
            self.build_graph()
        self.pagerank_scores = nx.pagerank(self.graph)

    def calculate_tfidf(self, concept_name):
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:concept {name: $concept_name})-[:include_in]->(s:structure)
                RETURN s.name AS structure_name
            """, concept_name=concept_name)
            structures = [record["structure_name"] for record in result]
            tf = len(structures)
            idf_sum = 0
            for structure in structures:
                result = session.run("""
                    MATCH (c:concept)-[:include_in]->(s:structure {name: $structure_name})
                    RETURN COUNT(DISTINCT c) AS concept_count
                """, structure_name=structure)
                concept_count = result.single()["concept_count"]
                idf = math.log(1 + 1 / (concept_count + 1))
                idf_sum += idf
            return tf * idf_sum

    def softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def get_concept_scores(self, concept_name):
        if self.pagerank_scores is None:
            self.calculate_pagerank()
        pagerank_score = self.pagerank_scores.get(concept_name, 0)
        tfidf_score = self.calculate_tfidf(concept_name)
        return {
            "concept_name": concept_name,
            "pagerank_score": pagerank_score,
            "tfidf_score": tfidf_score
        }

    def concept_fact_richness(self, concept_name, alpha=0.5):
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:concept {name: $concept_name})
                OPTIONAL MATCH (f:fact)-[:is_a]->(c)
                WITH COLLECT(f) AS direct_facts
                UNWIND direct_facts AS df
                OPTIONAL MATCH (df)-[]->(f2:fact)
                WHERE f2 <> df AND NOT f2 IN direct_facts
                RETURN SIZE(direct_facts) AS direct_fact_count,
                       COUNT(DISTINCT f2) AS connected_fact_count
            """, concept_name=concept_name)
            record = result.single()
            if record:
                n1 = record["direct_fact_count"]
                n2 = record["connected_fact_count"]
                richness = n1 + alpha * n2
                return {
                    "concept": concept_name,
                    "direct_facts": n1,
                    "connected_facts": n2,
                    "richness_score": richness
                }
            else:
                return {
                    "concept": concept_name,
                    "direct_facts": 0,
                    "connected_facts": 0,
                    "richness_score": 0
                }

    def get_concept_all_scores(self, concept_name, alpha=0.5):
        base_scores = self.get_concept_scores(concept_name)
        richness_result = self.concept_fact_richness(concept_name, alpha=alpha)
        return {
            "concept_name": concept_name,
            "pagerank_score": base_scores["pagerank_score"],
            "tfidf_score": base_scores["tfidf_score"],
            "richness_score": richness_result["richness_score"],
            "direct_facts": richness_result["direct_facts"],
            "connected_facts": richness_result["connected_facts"]
        }

    def get_concepts_average_score_and_sort(self, concept_names, alpha=0.5, a=1, b=1, c=1, d=0):
        all_scores = [self.get_concept_all_scores(name, alpha=alpha) for name in concept_names]
        pagerank_list = np.array([s["pagerank_score"] for s in all_scores])
        tfidf_list = np.array([s["tfidf_score"] for s in all_scores])
        richness_list = np.array([s["richness_score"] for s in all_scores])
        pagerank_softmax = self.softmax(pagerank_list)
        tfidf_softmax = self.softmax(tfidf_list)
        richness_softmax = self.softmax(richness_list)
        weight_sum = a + b + c 
        results = []
        for i, s in enumerate(all_scores):
            avg_score = (a * pagerank_softmax[i] + b * tfidf_softmax[i] + c * richness_softmax[i]) / weight_sum
            origin_score = avg_score.copy()
            # 隨機調整分數
            variation = random.uniform(-1, 1)*d
            avg_score = avg_score + variation
            results.append({
                "concept_name": s["concept_name"],
                "pagerank_softmax": pagerank_softmax[i],
                "tfidf_softmax": tfidf_softmax[i],
                "richness_softmax": richness_softmax[i],
                "avg_score": avg_score,
                "pagerank": s["pagerank_score"],
                "tfidf": s["tfidf_score"],
                "richness": s["richness_score"],
                "origin_score": origin_score
            })
        sorted_results = sorted(results, key=lambda x: x["avg_score"], reverse=True)
        return sorted_results

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
    
    

if __name__ == "__main__":
    uri="bolt://localhost:7688"
    username="neo4j"
    password=""
    with ConceptScorer(uri,username,password) as scorer:
        concepts = ['天氣', '降雨', '日期', '職業']
        # 例如：PageRank 權重 2，TF-IDF 權重 1，Richness 權重 1
        sorted_results = scorer.get_concepts_average_score_and_sort(concepts, alpha=0.3, a=1, b=1, c=1, d=0.2)
        print("加權綜合分數排序：")
        for r in sorted_results:
            print(f"{r['concept_name']} → 加權平均: {r['avg_score']:.4f} | PageRank: {r['pagerank_softmax']:.4f} | TF-IDF: {r['tfidf_softmax']:.4f} | Richness: {r['richness_softmax']:.4f} | 原始分數: {r['origin_score']:.4f}")