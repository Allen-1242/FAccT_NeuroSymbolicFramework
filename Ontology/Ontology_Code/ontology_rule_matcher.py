"""
ontology_rule_linker.py
-----------------------
Reads Testing_Final_Results.json, extracts only inner ontology matches,
matches them to snap_rules.json using 100% coverage (strict match),
and saves enriched results to Testing_Final_Linked.json.
"""

import json
from pathlib import Path

# ---------- File paths ----------
RESULTS_PATH = Path("/home/dev/Masters_Thesis/Neuro_Symbolic/Ontology_Identified.json")
RULES_PATH   = Path("/home/dev/Masters_Thesis/Neuro_Symbolic/snap_rules.json")
OUTPUT_PATH  = Path("/home/dev/Masters_Thesis/Neuro_Symbolic/Identified_Rules.json")

# ---------- Rule matcher ----------
def match_rules_from_concepts(ontology_result, rules):
    """
    Given a list of ontology concepts and a list of rules,
    returns all rules whose appliesTo fields are fully covered (100%) by the ontology concepts.
    """
    ontology_nodes = set(ontology_result)
    matched_rules = []

    for rule in rules:
        rule_concepts = set(rule.get("appliesTo", []))
        if not rule_concepts:
            continue

        coverage = len(rule_concepts & ontology_nodes) / len(rule_concepts)
        if coverage == 1.0:
            rule["coverage"] = 1.0
            matched_rules.append(rule)

    return matched_rules

# ---------- Load input files ----------
print("Loading data...")
results = json.loads(RESULTS_PATH.read_text())
rules   = json.loads(RULES_PATH.read_text())
print(f"Loaded {len(results)} test cases and {len(rules)} rules.\n")

# ---------- Main linking loop ----------
linked_results = []

for i, case in enumerate(results, start=1):
    print(f"=== CASE {i}: {case.get('rule_id')} ===")

    match_result = case.get("match_result", {})
    if not match_result:
        print("No ontology result found. Skipping.\n")
        continue

    #Only inner ontology matches
    ontology_nodes = [im["node"] for im in match_result.get("inner_matches", []) if im.get("node")]
    if not ontology_nodes:
        print("No inner ontology matches. Skipping.\n")
        continue

    # Match only full-coverage rules
    matched = match_rules_from_concepts(ontology_nodes, rules)

    # Attach results
    case["ontology_nodes"] = ontology_nodes
    case["matched_rules"] = matched
    linked_results.append(case)

    print(f"Inner ontology nodes: {ontology_nodes}")
    print(f"Matched {len(matched)} full-coverage rules.\n")

# ---------- Save enriched output ----------
OUTPUT_PATH.write_text(json.dumps(linked_results, indent=2))
print(f"\nLinked results saved to: {OUTPUT_PATH.resolve()}\n")