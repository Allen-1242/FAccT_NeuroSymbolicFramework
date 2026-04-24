from neo4j import GraphDatabase
import time

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "71ul12z9"))

# Dummy LLM client – replace with your actual local LLM call
class DummyLLM:
    def classify_relation(self, src_text, dst_text, raw_type):
        return {"new_relation": "LIMITATION"}  # placeholder

llm_client = DummyLLM()

def enrich_part_5001(session, llm_client, limit=10):
    result = session.run("""
    MATCH (a:FederalSection)-[r:REFERS_SECTION|REFERS_USC]->(b)
    WHERE a.citation STARTS WITH "7 CFR § 5001"
    AND (r.enriched IS NULL OR r.enriched = false)
    RETURN a.uid AS src_uid, a.citation AS src_cite, a.text AS src_text,
        b.uid AS dst_uid, b.citation AS dst_cite, b.text AS dst_text,
        type(r) AS rawType
    LIMIT $limit
    """, limit=limit)

    edges = result.data()
    if not edges:
        print("No more edges to enrich in Part 5001.")
        return False

    for rec in edges:
        new_rel = llm_client.classify_relation(
            src_text=rec["src_text"],
            dst_text=rec["dst_text"],
            raw_type=rec["rawType"]
        )["new_relation"]

        session.run(f"""
        MATCH (a {{uid:$src}}), (b {{uid:$dst}})
        MERGE (a)-[:{new_rel} {{from:"LLM"}}]->(b);

        MATCH (a {{uid:$src}})-[r:{rec['rawType']}]->(b {{uid:$dst}})
        SET r.enriched = true;
        """, src=rec["src_uid"], dst=rec["dst_uid"])

        print(f"Enriched {rec['src_cite']} -> {rec['dst_cite']} as {new_rel}")
        time.sleep(0.2)  # gentle pacing

    return True


# Run loop until all Part 5001 edges enriched
with driver.session() as session:
    while enrich_part_5001(session, llm_client, limit=5):
        pass

driver.close()
