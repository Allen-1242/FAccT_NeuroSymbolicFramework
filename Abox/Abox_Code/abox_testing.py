# abox_tester_json.py
# ------------------------------------------------------------
# ABox Tester for SNAP XAI Framework (Updated)
# Executes legal consistency reasoning on test case facts
# and compares solver outcomes against ground-truth annotations.
# ------------------------------------------------------------

import json
from pathlib import Path
from SMT_solver import run_reasoning

# ---------- Paths ----------
BASE = Path("/home/dev/Masters_Thesis/Neuro_Symbolic")
TESTING_PATH = BASE / "Testing" / "Testing_Final.json"
DOMAIN_PATH = BASE / "snap_domain.json"
RULES_PATH = BASE / "snap_rules.json"
RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ---------- Config ----------
CASE_INDEX = 0  # <--- Change to test different cases

if __name__ == "__main__":

    # --- Load testing dataset ---
    cases = json.loads(TESTING_PATH.read_text())
    print(f"Loaded {len(cases)} test cases.")

    # --- Select case ---
    case = cases[CASE_INDEX]
    facts = case.get("fact_pattern", {})
    explanation = case.get("agency_explanation", "")
    expected = case.get("expected", {})
    expected_label = expected.get("sat_unsat")

    print(f"\n=== RUNNING CASE #{CASE_INDEX} ===")
    print(f"Case ID: {case.get('case_id')}")
    print(f"Category: {case.get('category')}")
    print("Agency Explanation:", explanation)

    print("\nFacts:")
    for k, v in facts.items():
        print(f"  {k}: {v}")

    # --- Run reasoning ---
    print("\nRunning solver...")
    result = run_reasoning(
        str(DOMAIN_PATH),
        str(RULES_PATH),
        facts
    )

    solver_outcome = result.get("solver_result")
    match_status = "MATCH" if solver_outcome == expected_label else "MISMATCH"

    # --- Display result ---
    print("\n=== SMT RESULT ===")
    print(json.dumps(result, indent=2))
    print(f"\nExpected: {expected_label} | Got: {solver_outcome} → {match_status}")

    # --- Save final report ---
    report = {
        "case_index": CASE_INDEX,
        "case_id": case.get("case_id"),
        "category": case.get("category"),
        "facts": facts,
        "agency_explanation": explanation,
        "expected_sat_unsat": expected_label,
        "expected_violated_rules": expected.get("violated_rules"),
        "solver_outcome": solver_outcome,
        "match_status": match_status,
        "smt_result": result
    }

    output_file = RESULTS_DIR / f"abox_case_{CASE_INDEX}_report.json"
    output_file.write_text(json.dumps(report, indent=2))
    print(f"\n✔ Report written to {output_file}\n")
