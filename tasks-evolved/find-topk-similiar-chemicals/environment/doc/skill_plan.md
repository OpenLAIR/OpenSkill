# Skill Creation Plan

**Task**: Build a Python function that extracts chemical names from a PDF, resolves them to SMILES via PubChem, computes Morgan fingerprint Tanimoto similarity against a target molecule, and returns the top-k most similar chemicals sorted by descending similarity with alphabetical tie-breaking.

**Rationale**: The task has three distinct functional domains: (1) extracting chemical names from a PDF, (2) converting chemical names to molecular representations via PubChem, and (3) computing fingerprint-based similarity and ranking results. However, since the pipeline is tightly coupled and the background research document provides a near-complete unified solution, decomposing into 2 skills—one for PDF extraction/name resolution and one for similarity computation/ranking—provides clean separation without over-decomposition.

**Number of skills**: 2

---

## Skill 1: evo-chem-pdf-extraction

**Description**: Extracts chemical names from a PDF file and resolves them to SMILES strings using PubChemPy. Handles PDF parsing with pdfplumber, text cleaning, and PubChem API rate limiting with retries.

**Responsibility**: PDF text extraction, chemical name parsing/cleaning, and chemical name to SMILES resolution via PubChem API. Does NOT compute similarity.

**Key functions**: `extract_chemicals_from_pdf`, `resolve_name_to_smiles`, `clean_and_parse_chemical_names`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-chem-pdf-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-chem-tanimoto-similarity

**Description**: Computes Morgan fingerprint-based Tanimoto similarity between molecules using RDKit 2025+ APIs, and provides the top-k ranking pipeline with proper tie-breaking. Integrates with the PDF extraction skill to form the complete solution.

**Responsibility**: SMILES to RDKit Mol conversion, Morgan fingerprint generation using the modern rdFingerprintGenerator API (radius=2, fpSize=2048, includeChirality=True), Tanimoto similarity computation, top-k sorting with descending similarity and alphabetical tie-breaking, and the main `topk_tanimoto_similarity_molecules` function.

**Key functions**: `generate_fingerprint`, `compute_tanimoto_similarity`, `topk_tanimoto_similarity_molecules`

**Depends on**: evo-chem-pdf-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-chem-tanimoto-similarity/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
