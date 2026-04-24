"""
two_tier_matcher.py
-------------------
Sentence-level matching → clause-level matching
Applies cosine cutoff (0.85) and prints structured results to terminal.
"""

import json, numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import spacy

# ---------- Load models ----------
model = SentenceTransformer("intfloat/e5-large-v2")
nlp = spacy.load("en_core_web_sm")

def cosine(a, b):
    a, b = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

# ---------- Config ----------
CUTOFF = 0.80
ONTOLOGY_PATH = Path("snap_ontology_with_embeddings_new.json")

# ---------- Load ontology ----------
ontology = json.loads(ONTOLOGY_PATH.read_text())

# ---------- Input explanation ----------
explanation = """
"Program rules require that every person applying for benefits be either a U.S. citizen or a qualified noncitizen, 
such as a lawful permanent resident or refugee. Because one household member does not meet these citizenship or 
immigration criteria, the household cannot be approved for participation in the program."""

# ---------- STEP 1: Split into sentences ----------
doc = nlp(explanation)
sentences = [s.text.strip() for s in doc.sents if len(s.text.strip()) > 10]
print(f"\nExtracted sentences ({len(sentences)}):\n", sentences)

# ---------- STEP 2: Embed sentences ----------
sent_embs = model.encode(sentences, normalize_embeddings=True)

# ---------- STEP 3: Outer (sentence-level) matching ----------
outer_scores = {node: 0 for node in ontology}
for sent, emb in zip(sentences, sent_embs):
    for node, data in ontology.items():
        score = cosine(emb, np.array(data["embedding"], dtype=np.float32))
        if score > outer_scores[node]:
            outer_scores[node] = score

# ---------- STEP 4: Select best outer node ----------
best_outer, best_outer_score = max(outer_scores.items(), key=lambda x: x[1])
print("\n================ SENTENCE-LEVEL OUTER MATCHING ================\n")
for node, score in sorted(outer_scores.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"{node:45} (score={score:.3f})")

print(f"\nBest outer node: {best_outer} (score={best_outer_score:.3f})")

# ---------- STEP 5: Select the best sentence for that node ----------
best_sentence_idx = np.argmax([
    cosine(emb, np.array(ontology[best_outer]["embedding"], dtype=np.float32))
    for emb in sent_embs
])
best_sentence = sentences[best_sentence_idx]
print(f"\nSelected sentence for inner matching:\n{best_sentence}\n")

# ---------- STEP 6: Split into clauses ----------
doc_clause = nlp(best_sentence)
clauses = [c.text.strip() for c in doc_clause.sents if len(c.text.strip()) > 5]
print(f"Extracted clauses ({len(clauses)}):\n", clauses)

# ---------- STEP 7: Clause embeddings ----------
clause_embs = model.encode(clauses, normalize_embeddings=True)

# ---------- STEP 8: Inner (clause-level) matching ----------
inner_nodes = ontology[best_outer].get("subtypes", {})
inner_scores = {sub: 0 for sub in inner_nodes}

for clause, emb in zip(clauses, clause_embs):
    for sub, node in inner_nodes.items():
        score = cosine(emb, np.array(node["embedding"], dtype=np.float32))
        if score > inner_scores[sub]:
            inner_scores[sub] = score

# ---------- STEP 9: Filter + rank results ----------
ranked_inner = [
    (sub, s) for sub, s in sorted(inner_scores.items(), key=lambda x: x[1], reverse=True)
    if s >= CUTOFF
]

print("\n================ CLAUSE-LEVEL INNER MATCHING (≥0.85) ================\n")
for sub, score in ranked_inner:
    print(f"{sub:45} (score={score:.3f})")

# ---------- STEP 10: Summary JSON (in-memory only) ----------
result = {
    "outer_node": best_outer,
    "outer_score": round(best_outer_score, 3),
    "inner_matches": [
        {"node": sub, "score": round(score, 3)} for sub, score in ranked_inner
    ]
}

print("\n================ STRUCTURED SUMMARY ================\n")
print(json.dumps(result, indent=2))
print("\n✅ Pipeline complete (no files written)\n")