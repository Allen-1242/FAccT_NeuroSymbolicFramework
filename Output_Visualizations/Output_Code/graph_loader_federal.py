from neo4j import GraphDatabase
import json, re, os

# --- Neo4j connection ---
uri = "bolt://localhost:7687"
user = "neo4j"
password = "71ul12z9"
driver = GraphDatabase.driver(uri, auth=(user, password))

# --- Relationship map ---
RELATION_MAP = {
    "sections": "REFERS_SECTION",
    "parts": "REFERS_PART",
    "subparts": "REFERS_SUBPART",
    "usc": "REFERS_USC"
}

# --- Ontology-aligned node labels ---
NODE_LABELS = {
    "title": "LegalWork",
    "part": "LegalWork",
    "subpart": "LegalWork",
    "section": "LegalExpression",
    "paragraph": "LegalExpression"
}

# --- Normalize references ---
def normalize_reference(src, dst):
    dst = dst.strip()
    if "CFR" in dst or "U.S.C." in dst:
        return dst
    # Rebuild partial citations based on context
    section_match = re.match(r"(\d+) CFR § (\d+)", src)
    if dst.startswith(".") and section_match:
        return f"{section_match.group(1)} CFR § {section_match.group(2)}{dst}"
    part_match = re.match(r"(\d+) CFR Part (\d+)", src.replace("§", "Part"))
    if part_match and re.match(r"\d+\.\d+", dst):
        return f"{part_match.group(1)} CFR § {dst}"
    return dst

# --- Sanitize node props (Neo4j accepts only primitives) ---
def sanitize_props(d):
    clean = {}
    for k, v in d.items():
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
            clean[k] = v
    return clean

# --- Batch node insertion ---
def batch_nodes(session, label, data):
    session.run(f"""
    UNWIND $rows AS row
    MERGE (n:{label} {{uid: row.uid}})
    SET n += row.props
    """, rows=data)

# --- BELONGS_TO edges (child → parent) ---
def batch_belongs(session, data):
    session.run("""
    UNWIND $rows AS row
    MATCH (child {uid: row.child_uid})
    MATCH (parent {uid: row.parent_uid})
    MERGE (child)-[:HAS_COMPONENT]->(parent)
    """, rows=data)

# --- Reference edges ---
def batch_refs(session, rel_type, data):
    session.run(f"""
    UNWIND $rows AS row
    MATCH (a {{uid: row.src}})
    MATCH (b {{citation: row.dst}})
    MERGE (a)-[:{rel_type}]->(b)
    """, rows=data)

# --- Main loader ---
def load_legal_system(json_file, batch_size=1000, limit=None):
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"File not found: {json_file}")

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if limit:
        data = data[:limit]
        print(f"⚙️ Limiting to first {limit} entries")

    with driver.session() as session:
        # --- Pass 1: Create nodes ---
        buffer = []
        count = 0

        for entry in data:
            label = NODE_LABELS.get(entry.get("node_type", ""), "LegalExpression")
            props = sanitize_props(entry)
            buffer.append({"uid": entry["uid"], "props": props})

            if len(buffer) >= batch_size:
                batch_nodes(session, label, buffer)
                count += len(buffer)
                print(f"Inserted {count} nodes...")
                buffer = []

        if buffer:
            batch_nodes(session, label, buffer)
            count += len(buffer)
            print(f"Inserted final {len(buffer)} nodes. Total: {count}")

        # --- Pass 2: BELONGS_TO (HAS_COMPONENT) edges ---
        edges = []
        count_edges = 0
        for entry in data:
            if entry.get("node_type") == "section":
                for para in entry.get("paragraphs", []):
                    edges.append({"child_uid": para["uid"], "parent_uid": entry["uid"]})
                    if len(edges) >= batch_size:
                        batch_belongs(session, edges)
                        count_edges += len(edges)
                        print(f"Created {count_edges} HAS_COMPONENT edges...")
                        edges = []

        if edges:
            batch_belongs(session, edges)
            count_edges += len(edges)
            print(f"Created final {len(edges)} HAS_COMPONENT edges. Total: {count_edges}")

        # --- Pass 3: REFERS_* edges ---
        ref_buffer = []
        count_refs = 0

        for entry in data:
            node_type = entry.get("node_type")
            refs_dict = entry.get("references", {})
            for ref_type, ref_list in refs_dict.items():
                rel_type = RELATION_MAP.get(ref_type, "REFERS_TO")
                for ref in ref_list:
                    dst = normalize_reference(entry.get("citation", ""), ref)
                    ref_buffer.append({"src": entry["uid"], "dst": dst})
                    if len(ref_buffer) >= batch_size:
                        batch_refs(session, rel_type, ref_buffer)
                        count_refs += len(ref_buffer)
                        print(f"Created {count_refs} {rel_type} edges...")
                        ref_buffer = []

        if ref_buffer:
            # Use last rel_type safely
            rel_type = RELATION_MAP.get(ref_type, "REFERS_TO")
            batch_refs(session, rel_type, ref_buffer)
            count_refs += len(ref_buffer)
            print(f"Created final {len(ref_buffer)} REFERS_* edges. Total: {count_refs}")

    print("\n✅ Legal system successfully loaded into Neo4j.")

# --- Run example ---
if __name__ == "__main__":
    load_legal_system(
        "/home/dev/Masters_Thesis/Legal_Documents/title7_flat.json",
        batch_size=1000,
        limit=None
    )
    driver.close()
