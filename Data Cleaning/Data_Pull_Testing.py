from neo4j import GraphDatabase
import json

uri = "bolt://localhost:7687"
user = "neo4j"
password = "71ul12z9"

driver = GraphDatabase.driver(uri, auth=(user, password))

with open("title7.json", "r", encoding="utf-8") as f:
    data = json.load(f)

with driver.session() as session:
    for entry in data: 
        citation = entry["citation"]
        text = entry.get("text", "")
        refs = entry.get("references", {})

        print(f"Creating node: {citation}")
        session.run(
            """
            MERGE (r:Regulation {citation:$citation})
            SET r.text=$text,
                r.main_section=$main_section,
                r.subsection=$subsection,
                r.jurisdiction="federal",
                r.system="CFR"
            """,
            citation=citation,
            text=text,
            main_section=entry.get("main_section", ""),
            subsection=entry.get("subsection", "")
        )

        # Loop over references
        for ref_type, ref_list in refs.items():
            for ref in ref_list:
                print(f"  Creating edge ({ref_type}): {citation} -> {ref}")
                session.run(
                    """
                    MERGE (r2:Regulation {citation:$ref})
                    MERGE (r:Regulation {citation:$citation})
                    MERGE (r)-[:REFERS_TO {type:$ref_type}]->(r2)
                    """,
                    citation=citation,
                    ref=ref,
                    ref_type=ref_type
                )

driver.close()
print(" Done inserting sample")
