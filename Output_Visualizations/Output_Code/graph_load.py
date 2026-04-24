import json
from neo4j import GraphDatabase

# === CONFIG ===
json_path = "/home/dev/Masters_Thesis/Laws/mpp_section_sub_embeddings.json"
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "71ul12z9"
neo4j_database = "mpp"  # Set your DB name here

# === CONNECT ===
driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

# === INDEX CREATION (run once) ===
def create_indexes(session):
    session.run("CREATE INDEX mpp_section_index IF NOT EXISTS FOR (n:MPPSection) ON (n.citation)")
    session.run("CREATE INDEX mpp_subsection_index IF NOT EXISTS FOR (n:MPPSubsection) ON (n.citation)")

# === LOADER FUNCTION ===
def load_mpp(tx, entry):
    citation = entry["citation"]
    main_section = entry.get("main_section", "")
    subsection = entry.get("subsection", "")
    text = entry.get("text", "")
    embedding_input = entry.get("embedding_input", "")

    # --- Create subsection node ---
    tx.run("""
        MERGE (s:MPPSubsection {citation: $citation})
        SET s.main_section   = $main_section,
            s.subsection     = $subsection,
            s.text           = $text,
            s.embedding_input= $embedding_input
        """, 
        citation=citation,
        main_section=main_section,
        subsection=subsection,
        text=text,
        embedding_input=embedding_input
    )

    # --- Create parent section node & link ---
    if main_section:
        tx.run("""
            MERGE (sec:MPPSection {citation: $main_section})
            MERGE (s:MPPSubsection {citation: $citation})
            MERGE (s)-[:SUBSECTION_OF]->(sec)
            """,
            citation=citation,
            main_section=main_section
        )

    # --- Handle references ---
    for ref in entry.get("references") or []:
        ref_val = ref["ref"] if isinstance(ref, dict) else ref
        ref_citation = f"MPP §{ref_val}" if not str(ref_val).startswith("MPP §") else ref_val
        tx.run("""
            MERGE (t:MPPSection {citation:$ref})
            MERGE (s:MPPSubsection {citation:$citation})
            MERGE (s)-[:REFERS_TO {type:'MPP'}]->(t)
            """,
            citation=citation,
            ref=ref_citation
        )

# === MAIN UPLOAD SCRIPT ===
def main():
    print("Loading JSON...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("JSON entries found:", len(data))

    with driver.session() as session:
        create_indexes(session)
        print(f"Uploading {len(data)} entries...")
        for i, entry in enumerate(data, 1):
            session.execute_write(load_mpp, entry)
            if i % 500 == 0:
                print(f"  → {i} subsections loaded...")
        print("Import complete!")

if __name__ == "__main__":
    main()
