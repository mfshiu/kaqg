import json
from neo4j import GraphDatabase
import threading



class KnowledgeGraph:
    _facts = {}
    _facts_lock = threading.Lock()
    
    
    def __init__(self, uri="bolt://localhost:7687", auth=None):
        self.driver = GraphDatabase.driver(uri, auth=auth)


    def close(self):
        self.driver.close()

    
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
                
                
    def merge_triplets(self, file_id, page_number, triplets):
        """Merges nodes and relationships, ensuring properties like page_number and aliases are updated."""
        with self.driver.session() as session:
            for triplet in triplets:
                subject = triplet[0]
                predicate = triplet[1]
                obj = triplet[2]

                # Merge subject node and update properties (replacing aliases)
                session.run(
                    f"""
                    MERGE (s:`{subject.get('type', 'Entity')}` {{name: $subject_name}})
                    SET s.file_id = $file_id,
                        s.page_number = $page_number,  // ✅ Ensures page_number is updated
                        s.aliases = $subject_aliases  // ✅ Directly replaces aliases
                    """,
                    subject_name=subject["name"],
                    file_id=file_id,
                    page_number=page_number,
                    subject_aliases=subject.get("aliases", [])
                )

                # Merge object node and update properties (replacing aliases)
                session.run(
                    f"""
                    MERGE (o:`{obj.get('type', 'Entity')}` {{name: $object_name}})
                    SET o.file_id = $file_id,
                        o.page_number = $page_number,  // ✅ Ensures page_number is updated
                        o.aliases = $object_aliases  // ✅ Directly replaces aliases
                    """,
                    object_name=obj["name"],
                    file_id=file_id,
                    page_number=page_number,
                    object_aliases=obj.get("aliases", [])
                )

                # Merge relationship to avoid duplication
                session.run(
                    f"""
                    MATCH (s:`{subject.get('type', 'Entity')}` {{name: $subject_name}}),
                        (o:`{obj.get('type', 'Entity')}` {{name: $object_name}})
                    MERGE (s)-[r:`{predicate["name"]}`]->(o)
                    """,
                    subject_name=subject["name"],
                    object_name=obj["name"]
                )


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
    kg.close()
