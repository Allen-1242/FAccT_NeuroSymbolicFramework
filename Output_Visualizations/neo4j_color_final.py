import json
from neo4j import GraphDatabase
from pathlib import Path

# Load solver report
report_path = "/home/dev/Masters_Thesis/Neuro_Symbolic/results/abox_case_0_report.json"
report = json.loads(Path(report_path).read_text())

# satisfied lives under smt_result
satisfied = report.get("smt_result", {}).get("satisfied", [])
satisfied_citations = list({v["citation"] for v in satisfied})

print("SATISFIED citations detected:", satisfied_citations)

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "71ul12z9"),
    encrypted=False
)

with driver.session() as session:
    for citation in satisfied_citations:
        result = session.run("""
            MATCH (sub:MPPSubsection {citation: $citation})
            SET sub:SATISFIED
            WITH sub
            OPTIONAL MATCH (sub)-[:SUBSECTION_OF]->(sec:MPPSection)
            SET sec:SATISFIED
            RETURN sub.citation AS sub_cite,
                   labels(sub) AS sub_labels,
                   collect(DISTINCT sec.citation) AS sec_cites,
                   collect(DISTINCT labels(sec)) AS sec_labels
        """, citation=citation).single()

        if result:
            print("Subsection marked SATISFIED:", result["sub_cite"])
            print("   Subsection labels:", result["sub_labels"])
            print("Parent sections marked SATISFIED:", result["sec_cites"])
        else:
            print(f"No exact MPPSubsection match for citation: {citation}")

driver.close()

print("\n✨ Done: SATISFIED laws marked in Neo4j! 🎯")
