from z3 import *

# define your boolean symbols (concepts)
QualifiedHousehold = Bool('QualifiedHousehold')
Eligible = Bool('Eligible')
BenefitType_SNAP = Bool('BenefitType_SNAP')
HouseholdStatus_Family = Bool('HouseholdStatus_Family')

# build solver
s = Solver()

# encode rules (from your JSON)
rule1 = Implies(Not(QualifiedHousehold), Not(Eligible))
rule2 = Implies(And(BenefitType_SNAP, HouseholdStatus_Family), Eligible)

# add rules to solver
s.add(rule1, rule2)

# test a scenario (e.g., unqualified household)
s.push()
s.add(QualifiedHousehold == False)
if s.check() == sat:
    print("Rule 1 holds under this condition")
s.pop()

# test a scenario where family applies for SNAP
s.push()
s.add(BenefitType_SNAP, HouseholdStatus_Family)
if s.check() == sat:
    print("Rule 2 holds — family SNAP applicant is eligible")
s.pop()

# optional: check consistency of all rules
print("Solver status:", s.check())
print("Model:", s.model() if s.check() == sat else "Unsat / conflict")
