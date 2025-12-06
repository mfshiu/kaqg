import json
import os
from venv import logger
from neo4j import GraphDatabase
import threading

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))


class KnowledgeGraph:
    _facts = {}
    _facts_lock = threading.Lock()
    
    
    def __init__(self, uri="bolt://localhost:7687", auth=None):
        self.driver = GraphDatabase.driver(uri, auth=auth)


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    @staticmethod
    def serialize_node(node):
        serialized = {
            "element_id": node.element_id,   # Neo4j 唯一識別碼
            "labels": list(node.labels),    # 節點標籤
        }
        serialized.update(dict(node))  # 屬性
        
        return serialized


    def __is_node_exist(node_type, node_name, file_id, page_number):
        if file_id not in KnowledgeGraph._facts:
            with KnowledgeGraph._facts_lock:
                KnowledgeGraph._facts[file_id] = []

        file_facts = KnowledgeGraph._facts.get(file_id, [])
        if (fflen := len(file_facts)) <= page_number:
            new_size = max(page_number+1, max(10, fflen*2))
            with KnowledgeGraph._facts_lock:
                for _ in range(new_size - fflen):
                    file_facts.append(set())
            print(f"Extended list to {new_size} items, real size: {len(file_facts)}.")

        key = f"{node_type}-{node_name}"
        is_existing = key in file_facts[page_number]

        if is_existing:
            print(f"Node '{key}' already exists in page {page_number}.")
        else:
            with KnowledgeGraph._facts_lock:
                file_facts[page_number].add(key)

        return is_existing


    def _add_fact(session, subject_type, subject, file_id, page_number):
        if KnowledgeGraph.__is_node_exist(subject_type, subject["name"], file_id, page_number):
            return  # 已存在，跳過建立
        
        session.run(
            f"""
            CREATE (s:`{subject_type}` {{
                name: $subject_name,
                file_id: $file_id,
                page_number: $page_number,
                aliases: $subject_aliases
            }})
            """,
            subject_name=subject["name"],
            file_id=file_id,
            page_number=page_number,
            subject_aliases=subject.get("aliases", [])
        )


    def add_triplets(self, file_id, page_number, triplets):
        with self.driver.session() as session:
            for triplet in triplets:
                subject = triplet[0]
                predicate = triplet[1]
                obj = triplet[2]

                # Create or merge subject node
                if (subject_type := subject.get('type', 'Entity')) == 'fact':
                    KnowledgeGraph._add_fact(session, subject_type, subject, file_id, page_number)
                elif (subject_type := subject.get('type', 'Entity')) == 'structure':
                    session.run(
                        f"""
                        MERGE (s:`{subject_type}` {{name: $subject_name}})
                        SET s.file_id = $file_id
                        """,
                        subject_name=subject["name"],
                        file_id=file_id
                    )
                else:   # concept
                    session.run(
                        f"""
                        MERGE (s:`{subject_type}` {{name: $subject_name}})
                        SET s.file_id = $file_id,
                            s.aliases = $aliases
                        """,
                        subject_name=subject["name"],
                        file_id=file_id,
                        aliases=subject.get("aliases", [])
                    )

                # Create or merge object node
                if (object_type := obj.get('type', 'Entity')) == 'fact':
                    KnowledgeGraph._add_fact(session, object_type, obj, file_id, page_number)
                elif (object_type := obj.get('type', 'Entity')) == 'document':
                    session.run(
                        f"""
                        MERGE (o:`{object_type}` {{name: $object_name}})
                        SET o.file_id = $file_id,
                            o.metadata = $metadata
                        """,
                        object_name=obj["name"],
                        file_id=file_id,
                        metadata=json.dumps(obj.get("meta", None))
                    )
                elif (object_type := obj.get('type', 'Entity')) == 'structure':
                    session.run(
                        f"""
                        MERGE (o:`{object_type}` {{name: $object_name}})
                        SET o.file_id = $file_id
                        """,
                        object_name=obj["name"],
                        file_id=file_id
                    )
                else:   # concept
                    session.run(
                        f"""
                        MERGE (o:`{object_type}` {{name: $object_name}})
                        SET o.file_id = $file_id,
                            o.aliases = $aliases
                        """,
                        object_name=obj["name"],
                        file_id=file_id,
                        aliases=obj.get("aliases", [])
                    )

                # Merge relationship to avoid duplication
                session.run(
                    f"""
                    MATCH (s:`{subject_type}` {{name: $subject_name}}),
                        (o:`{object_type}` {{name: $object_name}})
                    MERGE (s)-[r:`{predicate["name"]}`]->(o)
                    """,
                    subject_name=subject["name"],
                    object_name=obj["name"]
                )
            
            
    def close(self):
        self.driver.close()
        

    def _query_concepts_tx(tx, parent_names):
        """
        供 session.execute_read() 呼叫的交易函式，
        會在 Neo4j 交易上下文(tx)中執行實際的 Cypher 查詢。
        """
        
        if not parent_names:
            logger.error("parent_names is empty.")
            return []

        doc_name = parent_names[0]
        if len(parent_names) == 1:
            # 只有 document，查詢與 document 有 :include_in 關係的 concept
            last_structure_var = structure_vars[-1]
            cypher_list = [f"MATCH (c:concept)-[:include_in]->({doc_name}:document)"]
        else:
            # 第 0 個是 document，其餘皆為 structure
            structure_names = parent_names[1:]

            # 產生結構節點變數 (s0, s1, s2, ...)
            structure_vars = [f"s{i}" for i in range(len(structure_names))]

            # 依序組合 Cypher
            # MATCH (doc:document {name: $docName})
            # MATCH (s0:structure {name: $structureName0})-[:part_of]->(doc)
            # ...
            # MATCH (c:concept)-[:include_in]->(最後一個 structure)
            # RETURN c.name
            cypher_list = [
                "MATCH (doc:document {name: $docName})"
            ]

            for i, s_name in enumerate(structure_names):
                if i == 0:
                    # 第 1 層 structure 連到 doc
                    cypher_list.append(
                        f"MATCH ({structure_vars[i]}:structure {{name: $structureName{i}}})-[:part_of]->(doc)"
                    )
                else:
                    # 之後的 structure 連到上一層 structure
                    cypher_list.append(
                        f"MATCH ({structure_vars[i]}:structure {{name: $structureName{i}}})-[:part_of]->({structure_vars[i-1]})"
                    )

            # 查詢與最後一層 structure 有 :include_in 關係的 concept
            last_structure_var = structure_vars[-1]
            cypher_list.append(
                f"MATCH (c:concept)-[:include_in]->({last_structure_var})"
            )
            
        cypher_list.append("RETURN DISTINCT c.name AS conceptName")
        final_cypher = "\n".join(cypher_list)

        # 設定查詢參數
        params = {"docName": doc_name}
        for i, s_name in enumerate(structure_names):
            params[f"structureName{i}"] = s_name

        # 執行查詢
        result = tx.run(final_cypher, **params)

        # 解析回傳紀錄，取出完整的 concept 節點
        concepts = [KnowledgeGraph.serialize_node(record["c"]) for record in result]
        logger.verbose(f"Query concepts: {concepts}")
        return concepts
        # # 解析回傳紀錄，取出 conceptName
        # concept_names = [record["conceptName"] for record in result]
        # return concept_names


    def query_concepts(self, parent_names):
        """
        傳入一組 parent_names，例如：
            [
                "2.專業技術人員職掌與工作倫理(甲乙級)",  # document
                "貳、廢棄物清理專業技術人員相關法規及其職掌",  # structure
                "一、廢棄物清理專業技術人員所涉相關法規"        # structure
            ]

        parent_names 從左至右，表示由上而下的階層關係:
        parent_names[i+1] :part_of parent_names[i]

        最後一個名稱 (parent_names[-1]) 為最末層的 structure 節點，
        查詢與該節點有 :include_in 關係的所有 concept。
        """
        with self.driver.session() as session:
            concepts = session.execute_read(
                KnowledgeGraph._query_concepts_tx, 
                parent_names=parent_names
            )
            return concepts


    def query_nodes_by_name(self, node_name, label=None):
        """ Returns a list of serialized nodes matching the given name and optional label. """
        query = "MATCH (n" + (":" + label if label else "") + " {name: $node_name}) RETURN n"
        
        with self.driver.session() as session:
            result = session.run(query, node_name=node_name)
            return [self.serialize_node(record["n"]) for record in result]
        

    def query_nodes_related_by(self, node_eid, relation=None, label=None):
        """ Returns a list of serialized nodes related to the given node by the given relation. """
        label_clause = f":{label}" if label else ""
        relation_clause = f":{relation}" if relation else ""
        
        query = f"""
        MATCH (m{label_clause})-[{relation_clause}]->(n)
        WHERE elementId(n) = $node_eid
        RETURN m
        """

        with self.driver.session() as session:
            result = session.run(query, node_eid=node_eid)
            return [self.serialize_node(record["m"]) for record in result]
        
        
    def query_nodes_relate_to(self, node_eid, relation=None, label=None):
        """ Returns a list of serialized nodes that the given node relates to via the specified relation. """
        label_clause = f":{label}" if label else ""
        relation_clause = f":{relation}" if relation else ""

        query = f"""
        MATCH (n)-[{relation_clause}]->(m{label_clause})
        WHERE elementId(n) = $node_eid
        RETURN m
        """

        with self.driver.session() as session:
            result = session.run(query, node_eid=node_eid)
            return [self.serialize_node(record["m"]) for record in result]


    def query_subsections(self, document, section_path=None):
        def _query_subsections(self, document, section_path=None):
            logger.verbose(f"Querying subsections for document: {document}, section_path: {section_path}")

            def fetch_all_subsections(session, parent_path):
                last_node = parent_path[-1]
                if last_node is None:
                    return [parent_path]

                query = """
                MATCH (sec:structure {name: $last_section})
                OPTIONAL MATCH (sub:structure)-[:part_of]->(sec)
                RETURN collect(sub) AS subsections
                """
                last_section = last_node["name"]
                record = session.run(query, last_section=last_section).single()
                if not record:
                    return [parent_path]

                subsections = [s for s in record["subsections"] if s is not None]

                all_paths = [parent_path]
                for sub in subsections:
                    all_paths.extend(fetch_all_subsections(session, parent_path + [sub]))
                return all_paths

            with self.driver.session() as session:

                # --- 有 section_path 的情況 ---
                if section_path:
                    initial_nodes = []
                    for section in section_path:
                        record = session.run(
                            "MATCH (sec:structure {name: $section}) RETURN sec",
                            section=section
                        ).single()

                        if record and record["sec"]:
                            initial_nodes.append(record["sec"])

                    if initial_nodes:
                        # 找到 structure，正常展開
                        all_paths = []
                        for n in initial_nodes:
                            all_paths.extend(fetch_all_subsections(session, [n]))
                        return all_paths

                    # ⭐ section_path 有值但找不到 structure → 你要的行為：
                    # ⭐⭐ 再呼叫一次，等同沒有 section_path ⭐⭐
                    logger.warning(
                        f"No structure found for section_path={section_path}, "
                        f"recursively fallback to query_subsections(document, None)."
                    )
                    return self.query_subsections(document, None)



                # --- section_path = None 的情況 ---
                record = session.run(
                    """
                    MATCH (doc:document {name: $document})
                    OPTIONAL MATCH (sec:structure)-[:part_of]->(doc)
                    RETURN collect(sec) AS sections
                    """,
                    document=document
                ).single()

                sections = []
                if record:
                    sections = [s for s in record["sections"] if s is not None]

                if not sections:
                    # 文件底下也沒有任何 structure，直接回傳空
                    logger.verbose(f"Document '{document}' has no structure nodes.")
                    return []

                all_paths = []
                for sec in sections:
                    all_paths.extend(fetch_all_subsections(session, [sec]))
                return all_paths

        # serialize 最終節點
        sectionss = _query_subsections(self, document, section_path)
        return [self.serialize_node(sections[-1]) for sections in sectionss]


    def session(self):
        return self.driver.session()
    

if __name__ == "__main__":
    # 測試數據
    data = {
        'file_id': 'file_id',
        'page_number': 2,
        'kg_name': 'ExampleKG',
        'triplets': [
            [
                {
                    "type": "fact",
                    "name": "冬天",
                    "aliases": ["winter", "coldseason"]
                },
                {
                    "name": "is_a"
                },
                {
                    "type": "concept",
                    "name": "季節",
                    "aliases": ["season", "period"]
                }
            ],
            [
                {
                    "type": "fact",
                    "name": "春天",
                    "aliases": ["spring", "warmseason"]
                },
                {
                    "name": "is_a"
                },
                {
                    "type": "concept",
                    "name": "季節",
                    "aliases": ["season", "period"]
                }
            ],
        ]
    }

    kg = KnowledgeGraph(uri='bolt://localhost:7688', auth=('neo4j', '!Qazxsw2'))
    kg.add_triplets(data['file_id'], data['page_number'], data['triplets'])
    
    data['page_number'] = 3
    kg.add_triplets(data['file_id'], data['page_number'], data['triplets'])
