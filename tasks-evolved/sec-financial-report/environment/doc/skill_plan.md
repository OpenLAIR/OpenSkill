# Skill Creation Plan

**Task**: Analyze SEC Form 13F-HR filings for Q2 and Q3 2025 to answer questions about hedge fund AUM, holdings, quarter-over-quarter changes, and top holders of specific stocks.

**Rationale**: The task is a focused 13F analysis pipeline where all questions rely on a shared set of data loading, entity resolution, and holdings analysis utilities. A single cohesive skill covering the 13F dataset toolkit minimizes overlap and matches the unified background research.

**Number of skills**: 1

---

## Skill 1: evo-sec13f-analyzer

**Description**: Toolkit for parsing SEC Form 13F-HR quarterly TSV datasets: load COVERPAGE/INFOTABLE/SUMMARYPAGE with proper dtypes, fuzzy-match fund manager names with RapidFuzz, retrieve fund AUM, aggregate unique equity holdings (filtering options), compare holdings across quarters, and rank top holders of a given CUSIP. Use whenever working with the /root/2025-q2 and /root/2025-q3 13F TSV files.

**Responsibility**: Provide all data loading, entity resolution, and holdings analytics utilities for SEC 13F datasets.

**Key functions**: `load_coverpage`, `load_infotable`, `load_summarypage`, `fuzzy_find_manager`, `get_fund_aum`, `get_fund_holdings`, `compare_holdings`, `top_holders_of_cusip`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-sec13f-analyzer/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
