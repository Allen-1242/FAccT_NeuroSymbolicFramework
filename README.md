Neuro-Symbolic Auditing Framework for Public Benefit Eligibility

A neuro-symbolic framework for auditing CalFresh (SNAP) eligibility determinations, combining OWL ontologies, Z3/SMT formal verification, and LLM-based reasoning to achieve 97.7% accuracy against judicial rulings. Presented at ACM FAccT 2026.

Overview:
The framework requires two types of input: (1) a statutory corpus encoding the legal rules that govern eligibility, and (2) real-world case data containing the agency's explanation, the determination outcome, and the factual circumstances of the applicant. The statutory corpus provides the legal standard against which explanations are evaluated; the case data provides the explanations and facts to be verified.
The statutory corpus comes from the CalFresh regulations in MPP Division 63, published by the California Department of Social Services (CDSS). These span chapters on eligibility criteria, benefit computation, and administrative procedures, stored as separate document files on the CDSS website. We downloaded, assembled, and cleaned them into a unified JSON structure for downstream processing. This corpus serves as the ground truth for ontology construction of the law.

Citation
bibtex@inproceedings{sunny2026neurosymbolic,
  title={Neuro-Symbolic Auditing Framework for Public Benefit Eligibility},
  author={Sunny, Allen and Sivan-Sevilla, Ido},
  booktitle={Proceedings of the 2026 ACM Conference on Fairness, Accountability, and Transparency (FAccT)},
  year={2026}
}
