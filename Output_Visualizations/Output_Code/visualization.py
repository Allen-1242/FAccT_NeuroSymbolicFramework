# push_reasoning_to_neo4j.py
import json
from neo4j import GraphDatabase

# --- Neo4j connection ---
uri = "bolt://localhost:7687"
user = "neo4j"
password = "71ul12z9"
driver = GraphDatabase.driver(uri, auth=(user, password))

# --- Load reasoning output ---
results_path = "/home/dev/Masters_Thesis/Neuro_Symbolic/results/chained_inference_report.json"
with open(results_path) as f:
    data = json.load(f)

violations = data.get("violations", [])
derived = data.get("derived_steps", [])

failed = [{"citation": v.get("citation")} for v in violations if v.get("citation")]
passed = [{"citation": d.get("citation")} for d in derived if d.get("citation")]

print(f"Loaded {len(passed)} passed, {len(failed)} failed rules from {results_path}")


# --- Neo4j helpers ---
def mark_nodes(tx, updates, status):
    query = f"""
    UNWIND $updates AS u
    MATCH (n)
    WHERE (n:MPPSection OR n:MPPSubsection)
      AND toLower(trim(n.citation)) = toLower(trim(u.citation))
    REMOVE n:Status_passed:Status_failed:Status_default
    SET n.status = '{status}', n:Status_{status}, n.last_updated = datetime()
    RETURN count(*) AS updated
    """
    # Neo4j fix: replace invalid OR with proper label test
    query = f"""
    UNWIND $updates AS u
    MATCH (n)
    WHERE (n:MPPSection OR n:MPPSubsection)
      AND toLower(trim(n.citation)) = toLower(trim(u.citation))
    REMOVE n:Status_passed:Status_failed:Status_default
    SET n.status = '{status}', n:Status_{status}, n.last_updated = datetime()
    RETURN count(*) AS updated
    """
    return tx.run(query, updates=updates).single()["updated"]


def reset_statuses(tx):
    query = """
    MATCH (n)
    WHERE n:MPPSection OR n:MPPSubsection
    REMOVE n:Status_passed:Status_failed:Status_default, n.status
    RETURN count(n) AS cleared
    """
    return tx.run(query).single()["cleared"]


# --- Push updates to Neo4j ---
with driver.session(database="neo4j") as session:
    cleared = session.execute_write(reset_statuses)
    print(f"🧹 Cleared {cleared} existing status labels/properties.")

    if passed:
        updated_passed = session.execute_write(mark_nodes, passed, "passed")
        print(f"Updated {updated_passed} passed nodes.")

    if failed:
        updated_failed = session.execute_write(mark_nodes, failed, "failed")
        print(f"Updated {updated_failed} failed nodes.")

    query_default = """
    MATCH (n)
    WHERE (n:MPPSection OR n:MPPSubsection)
      AND n.status IS NULL
    SET n.status = 'default', n:Status_default
    RETURN count(n) AS updated
    """
    updated_default = session.run(query_default).single()["updated"]
    print(f"🔵 Updated {updated_default} default nodes.")

driver.close()
print("Neo4j visualization update complete.")
