"""
two_tier_matcher.py
-------------------
Iterates through each test case in Testing_Final.json.
Performs sentence-level and clause-level ontology matching on llm_explanation.
Outputs structured results per case to terminal and saves all results to Testing_Final_Results.json.
"""

import json, numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import spacy

# ---------- Load models ----------
print("Loading models...")
model = SentenceTransformer("intfloat/e5-large-v2")
nlp = spacy.load("en_core_web_sm")

# ---------- Config ----------
CUTOFF = 0.85
ONTOLOGY_PATH = Path("/home/dev/Masters_Thesis/Neuro_Symbolic/snap_ontology_with_embeddings_new.json")
TEST_FILE = Path("/home/dev/Masters_Thesis/Neuro_Symbolic/Testing/Testing_Final.json")
OUTPUT_FILE = Path("Ontology_Identified.json")

# ---------- Helpers ----------
def cosine(a, b):
    a, b = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

# ---------- Load ontology + tests ----------
ontology = json.loads(ONTOLOGY_PATH.read_text())
tests = json.loads(TEST_FILE.read_text())

print(f"Loaded ontology with {len(ontology)} nodes.")
print(f"Loaded {len(tests)} test cases.\n")

# ---------- Core matching function ----------
def run_match(explanation: str):
    #Split into sentences
    doc = nlp(explanation)
    sentences = [s.text.strip() for s in doc.sents if len(s.text.strip()) > 10]
    if not sentences:
        return {"error": "No valid sentences extracted"}

    #Sentence embeddings
    sent_embs = model.encode(sentences, normalize_embeddings=True)

    #Outer (sentence-level) matching
    outer_scores = {node: 0 for node in ontology}
    for emb in sent_embs:
        for node, data in ontology.items():
            score = cosine(emb, np.array(data["embedding"], dtype=np.float32))
            if score > outer_scores[node]:
                outer_scores[node] = score

    best_outer, best_outer_score = max(outer_scores.items(), key=lambda x: x[1])

    # Select sentence best aligned to best_outer
    best_sentence_idx = np.argmax([
        cosine(emb, np.array(ontology[best_outer]["embedding"], dtype=np.float32))
        for emb in sent_embs
    ])
    best_sentence = sentences[best_sentence_idx]

    #Split best sentence into clauses
    doc_clause = nlp(best_sentence)
    clauses = [c.text.strip() for c in doc_clause.sents if len(c.text.strip()) > 5]

    #Clause embeddings
    clause_embs = model.encode(clauses, normalize_embeddings=True)

    #Inner (clause-level) matching
    inner_nodes = ontology[best_outer].get("subtypes", {})
    inner_scores = {sub: 0 for sub in inner_nodes}

    for emb in clause_embs:
        for sub, node in inner_nodes.items():
            score = cosine(emb, np.array(node["embedding"], dtype=np.float32))
            if score > inner_scores[sub]:
                inner_scores[sub] = score

    #Rank + filter
    ranked_inner = [
        (sub, s) for sub, s in sorted(inner_scores.items(), key=lambda x: x[1], reverse=True)
        if s >= CUTOFF
    ]

    return {
        "outer_node": best_outer,
        "outer_score": round(best_outer_score, 3),
        "inner_matches": [
            {"node": sub, "score": round(score, 3)} for sub, score in ranked_inner
        ],
        "num_sentences": len(sentences),
        "num_clauses": len(clauses)
    }

# ---------- Loop through test cases ----------
all_results = []

target_i = 1
for i, case in enumerate(tests, start=1):
    if i != target_i:
        continue  # skip all others
    print(f"\n================ CASE {i}: {case.get('rule_id')} ================\n")

    explanation = case.get("llm_explanation", "")
    result = run_match(explanation)
    case_result = {
        "rule_id": case.get("rule_id"),
        "expected_decision": case.get("expected_decision"),
        "expected_reason": case.get("expected_reason"),
        "purpose": case.get("purpose"),
        "match_result": result
    }
    all_results.append(case_result)

    # Print readable summary
    print(json.dumps(case_result, indent=2))

# ---------- Save results ----------
OUTPUT_FILE.write_text(json.dumps(all_results, indent=2))
print(f"\n================ ALL CASES COMPLETE ================\nResults saved to: {OUTPUT_FILE.resolve()}\n")
