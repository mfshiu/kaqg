import json
from neo4j import GraphDatabase
import threading



class KnowledgeGraph:
    _facts = {}
    _facts_lock = threading.Lock()
    
    
    def __init__(self, uri="bolt://localhost:7687", auth=None):
        self.driver = GraphDatabase.driver(uri, auth=auth)


    # def close(self):
    #     self.driver.close()

    
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
        try:
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
        finally:
            self.driver.close()
            

    def _query_concepts_tx(tx, parent_names):
        """
        供 session.execute_read() 呼叫的交易函式，
        會在 Neo4j 交易上下文(tx)中執行實際的 Cypher 查詢。
        """

        # 若只有一個名稱(只有 document、沒有任何 structure)，通常不會有 concept
        if len(parent_names) == 1:
            return []

        # 第 0 個是 document，其餘皆為 structure
        doc_name = parent_names[0]
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

        # 解析回傳紀錄，取出 conceptName
        concept_names = [record["conceptName"] for record in result]
        return concept_names


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
        try:
            with self.driver.session() as session:
                # 使用 session.execute_read() 呼叫查詢
                concept_names = session.execute_read(
                    KnowledgeGraph._query_concepts_tx, 
                    parent_names=parent_names
                )
                return concept_names
        finally:
            self.driver.close()



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
    # kg.close()
