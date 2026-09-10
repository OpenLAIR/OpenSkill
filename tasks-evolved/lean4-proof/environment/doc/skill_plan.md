# Skill Creation Plan

**Task**: Complete a Lean 4 proof that a recursively defined sequence S_n = S_{n-1} + 1/2^n (with S_0=1) satisfies S_n ≤ 2 for all n, starting from line 15 of a template file.

**Rationale**: This is a single-domain task requiring Lean 4 proof writing. The key challenge is reading the existing template, understanding its definitions and theorem statement, then crafting a proof using induction with appropriate Mathlib4 tactics. A single skill covering Lean 4 proof construction for recursive sequence inequalities is sufficient.

**Number of skills**: 1

---

## Skill 1: evo-lean4-recursive-sequence-inequality-proof

**Description**: Provides utilities and guidance for constructing Lean 4 proofs involving recursive sequences and geometric sum inequalities. Covers reading existing Lean template files, crafting induction-based proofs with closed-form intermediate lemmas, and using Mathlib4 tactics (norm_num, linarith, positivity, ring, field_simp, simp) to handle arithmetic over rationals with powers of 2.

**Responsibility**: Analyze the existing solution.lean template (definitions, imports, theorem statement), determine the correct proof strategy (direct induction via closed-form lemma S_n = 2 - 1/2^n, then inequality), generate the complete proof text starting at line 15, and write it to the file while preserving the prefix.

**Key functions**: `read_lean_template`, `generate_proof_body`, `write_proof_to_file`, `validate_lean_build`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-lean4-recursive-sequence-inequality-proof/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
