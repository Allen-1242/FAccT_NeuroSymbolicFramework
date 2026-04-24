import json
from neo4j import GraphDatabase

# === CONFIG ===
json_path = "/home/dev/Masters_Thesis/Python/obbb_policy_clauses_all.json"
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "71ul12z9"

driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

def load_policy_clause(tx, clause):
    # --- Create PolicyClause node ---
    tx.run("""
        MERGE (p:PolicyClause {id:$id})
        SET p.title   = $title,
            p.section = $section,
            p.text    = $text,
            p.topic   = $topic
        """, clause)

    # --- Link to MPP subsections ---
    for match in clause.get("matches", []):
        tx.run("""
            MATCH (p:PolicyClause {id:$id}),
                  (m:MPPSubsection {citation:$citation})
            MERGE (p)-[r:AFFECTS]->(m)
            SET r.score = $score
            """, {
                "id": clause["id"],
                "citation": match["citation"],
                "score": match["score"]
            })

def main():
    with open(json_path, "r", encoding="utf-8") as f:
        clauses = json.load(f)

    with driver.session() as session:
        for clause in clauses:
            session.execute_write(load_policy_clause, clause)

    print(f"✅ Uploaded {len(clauses)} OBBB Policy Clauses and their relationships!")

if __name__ == "__main__":
    main()
