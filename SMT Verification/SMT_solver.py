# SMT_solver.py
# ------------------------------------------------------------
# Minimal Z3-based reasoning core for SNAP ontology and rules
# Called directly from abox_tester_json.py
# ------------------------------------------------------------
from z3 import *
import json

# ---------- 1. Load domain and create Z3 symbols ----------
def load_symbols(domain_path):
    """
    Reads the ontology (domain) JSON and automatically defines Z3 symbols
    for all concept names and subtypes based on their conceptType.
    """
    with open(domain_path) as f:
        domain = json.load(f)
    symbols = {}
    for name, info in domain.items():
        ctype = (info.get("conceptType") or "").lower()
        if "num" in ctype:
            symbols[name] = Real(name)
        elif "string" in ctype or "cat" in ctype:
            symbols[name] = String(name)
        else:
            symbols[name] = Bool(name)

        # Handle subtypes if any
        for sub, subinfo in info.get("subtypes", {}).items():
            stype = (subinfo.get("conceptType") or "").lower()
            if "num" in stype:
                symbols[sub] = Real(sub)
            elif "string" in stype or "cat" in stype:
                symbols[sub] = String(sub)
            else:
                symbols[sub] = Bool(sub)
    return symbols


# ---------- 2. Load and parse logic rules ----------
def load_rules(rules_path, symbols):
    """
    Loads the rules JSON and safely evaluates each 'hasLogic' field
    into a Z3 Boolean expression using the defined symbols.
    Also retains citation and text for interpretability.
    """
    with open(rules_path) as f:
        rules_json = json.load(f)
    env = {
        "And": And, "Or": Or, "Not": Not, "Implies": Implies,
        "BoolVal": BoolVal, "RealVal": RealVal, "StringVal": StringVal,
        **symbols
    }
    parsed_rules = []
    for r in rules_json:
        logic = r.get("hasLogic")
        if not logic:
            continue
        try:
            expr = eval(logic, {"__builtins__": {}}, env)

            # Convert Implies(A, B) → And(A, B) to avoid vacuous truth
            if is_app(expr) and expr.decl().name() == "=>":
                ant = expr.arg(0)
                cons = expr.arg(1)
                expr = And(ant, cons)

            parsed_rules.append({
                "id": r["id"],
                "expr": expr,
                "citation": r.get("citation", ""),
                "text": r.get("hasText", "")
            })
        except Exception as e:
            print(f"⚠️  Skipped {r.get('id')}: {e}")
    print(f"Loaded {len(parsed_rules)} rules")
    return parsed_rules

#subset_ids = [
#   "Rule_ResidencyRequirement",
#    "Rule_StateResidencyRequirement"
#]

subset_ids = [
    None
]


def run_reasoning(domain_path, rules_path, facts, subset_ids=subset_ids):
    symbols = load_symbols(domain_path)
    all_rules = load_rules(rules_path, symbols)

    # --- Optionally limit to subset ---
    if subset_ids:
        rules = [r for r in all_rules if r["id"] in subset_ids]
        print(f"Using subset of {len(rules)} / {len(all_rules)} rules for reasoning.")
    else:
        rules = all_rules
        print(f"Using full rule set of {len(rules)} rules.")

    satisfied, violated = [], []

    # --- Evaluate each rule individually ---
    for rule in rules:
        rid, expr = rule["id"], rule["expr"]
        s = Solver()

        # assert known facts
        for k, v in facts.items():
            if v is None or k not in symbols:
                continue
            sym = symbols[k]
            try:
                if isinstance(sym, BoolRef):
                    s.add(sym == bool(v))
                elif isinstance(sym, ArithRef):
                    s.add(sym == float(v))
                elif isinstance(sym, SeqRef):
                    s.add(sym == str(v))
            except Exception:
                pass

        try:
            s.add(expr)
            res = s.check()
            if res == sat:
                satisfied.append({
                    "id": rid,
                    "citation": rule.get("citation", ""),
                    "text": rule.get("text", "")
                })
            else:
                violated.append({
                    "id": rid,
                    "citation": rule.get("citation", ""),
                    "text": rule.get("text", "")
                })
        except Exception as e:
            print(f"Could not test rule {rid}: {e}")

    # --- Global check over subset only ---
    s_global = Solver()
    for k, v in facts.items():
        if v is None or k not in symbols:
            continue
        sym = symbols[k]
        try:
            if isinstance(sym, BoolRef):
                s_global.add(sym == bool(v))
            elif isinstance(sym, ArithRef):
                s_global.add(sym == float(v))
            elif isinstance(sym, SeqRef):
                s_global.add(sym == str(v))
        except Exception:
            pass

    for rule in rules:
        s_global.add(rule["expr"])

    global_result = s_global.check()

    print("\n=== SMT Reasoning ===")
    print(f"Global SAT check: {global_result}")
    print(f"Rules satisfied: {len(satisfied)} | violated: {len(violated)}")

    return {
        "status": str(global_result),
        "satisfied": satisfied,
        "violated": violated
    }
