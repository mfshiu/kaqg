from neo4j import GraphDatabase



class KnowledgeGraph:
    def __init__(self, uri="bolt://localhost:7687", auth=None):
        self.driver = GraphDatabase.driver(uri, auth=auth)


    def close(self):
        self.driver.close()


    def add_triplets(self, source_type, file_id, page_number, triplets):
        with self.driver.session() as session:
            for triplet in triplets:
                subject = triplet[0]
                predicate = triplet[1]
                obj = triplet[2]

                # Create or merge subject node
                if (subject_type := subject.get('type', 'Entity')) == 'fact':
                    # Create subject node with dynamic label
                    session.run(
                        f"""
                        CREATE (s:`{subject_type}` {{
                            name: $subject_name,
                            source_type: $source_type,
                            file_id: $file_id,
                            page_number: $page_number,
                            aliases: $subject_aliases
                        }})
                        """,
                        subject_name=subject["name"],
                        source_type=source_type,
                        file_id=file_id,
                        page_number=page_number,
                        subject_aliases=subject.get("aliases", [])
                    )
                else:
                    # Merge subject node and update properties (replacing aliases)
                    session.run(
                        f"""
                        MERGE (s:`{subject_type}` {{name: $subject_name}})
                        SET s.source_type = $source_type,
                            s.file_id = $file_id,
                            s.page_number = $page_number,  // ✅ Ensures page_number is updated
                            s.aliases = $subject_aliases  // ✅ Directly replaces aliases
                        """,
                        subject_name=subject["name"],
                        source_type=source_type,
                        file_id=file_id,
                        page_number=page_number,
                        subject_aliases=subject.get("aliases", [])
                    )

                # Create or merge object node
                if (object_type := obj.get('type', 'Entity')) == 'fact':
                    # Create object node with dynamic label
                    session.run(
                        f"""
                        CREATE (o:`{object_type}` {{
                            name: $object_name,
                            source_type: $source_type,
                            file_id: $file_id,
                            page_number: $page_number,
                            aliases: $object_aliases
                        }})
                        """,
                        object_name=obj["name"],
                        source_type=source_type,
                        file_id=file_id,
                        page_number=page_number,
                        object_aliases=obj.get("aliases", [])
                    )
                else:
                    # Merge object node and update properties (replacing aliases)
                    session.run(
                        f"""
                        MERGE (o:`{object_type}` {{name: $object_name}})
                        SET o.source_type = $source_type,
                            o.file_id = $file_id,
                            o.page_number = $page_number,  // ✅ Ensures page_number is updated
                            o.aliases = $object_aliases  // ✅ Directly replaces aliases
                        """,
                        object_name=obj["name"],
                        source_type=source_type,
                        file_id=file_id,
                        page_number=page_number,
                        object_aliases=obj.get("aliases", [])
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
                
                
    def merge_triplets(self, source_type, file_id, page_number, triplets):
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
                    SET s.source_type = $source_type,
                        s.file_id = $file_id,
                        s.page_number = $page_number,  // ✅ Ensures page_number is updated
                        s.aliases = $subject_aliases  // ✅ Directly replaces aliases
                    """,
                    subject_name=subject["name"],
                    source_type=source_type,
                    file_id=file_id,
                    page_number=page_number,
                    subject_aliases=subject.get("aliases", [])
                )

                # Merge object node and update properties (replacing aliases)
                session.run(
                    f"""
                    MERGE (o:`{obj.get('type', 'Entity')}` {{name: $object_name}})
                    SET o.source_type = $source_type,
                        o.file_id = $file_id,
                        o.page_number = $page_number,  // ✅ Ensures page_number is updated
                        o.aliases = $object_aliases  // ✅ Directly replaces aliases
                    """,
                    object_name=obj["name"],
                    source_type=source_type,
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
        'source_type': 'pdf',
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
    kg.add_triplets(data['source_type'], data['file_id'], data['page_number'], data['triplets'])
    
    data['page_number'] = 3
    kg.add_triplets(data['source_type'], data['file_id'], data['page_number'], data['triplets'])
    # kg.merge_triplets(data['source_type'], data['file_id'], data['page_number'], data['triplets'])
    kg.close()
