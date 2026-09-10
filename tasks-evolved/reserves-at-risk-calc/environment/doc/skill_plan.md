# Skill Creation Plan

**Task**: Extract gold prices from IMF data, calculate log returns and volatilities, integrate with country reserve data, and compute Reserves at Risk (RaR) metrics in an Excel workbook using openpyxl and LibreOffice for formula evaluation.

**Rationale**: This task has three distinct concerns: (1) reading/exploring complex IMF spreadsheet data and the template workbook structure, (2) writing financial formulas and data into the correct cells across multiple sheets with openpyxl, and (3) forcing formula recalculation via headless LibreOffice. Since the data exploration feeds directly into the formula writing, and the LibreOffice recalculation is a simple final step, a 2-skill decomposition provides clean separation between data extraction/analysis and Excel formula construction/output.

**Number of skills**: 2

---

## Skill 1: evo-excel-data-extraction

**Description**: Utilities for exploring and extracting data from complex, multi-sheet Excel workbooks with irregular formatting (merged cells, variable header rows). Provides functions to discover sheet structure, locate specific commodities/countries, and extract time series data from IMF-style spreadsheets.

**Responsibility**: Reading and parsing source Excel files (IMF commodity prices and template workbook), handling merged cells, identifying header rows, extracting gold price time series, country reserve data, and understanding the template structure (row/column layout of Answer sheet, Value sheet, Volume sheet, Total Reserves sheet).

**Key functions**: `explore_sheet_structure`, `extract_gold_price_series`, `extract_country_reserve_data`, `get_merged_cell_value`, `find_header_row`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-excel-data-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-excel-financial-formulas

**Description**: Utilities for writing financial Excel formulas (log returns, rolling volatility, annualized volatility, XLOOKUP/INDEX+MATCH, RaR calculations) into openpyxl workbooks, copying data between sheets, and triggering LibreOffice headless recalculation to evaluate all formulas.

**Responsibility**: Writing all Excel formulas (LN, STDEV.S, SQRT, XLOOKUP/INDEX+MATCH) into the correct cells, populating gold price data into the Gold price sheet, filling Answer sheet blanks, handling cross-sheet references, computing Gold Price Exposure and RaR formulas, saving the workbook, and running LibreOffice headless to force formula recalculation.

**Key functions**: `write_gold_price_sheet`, `write_log_return_formulas`, `write_volatility_formulas`, `write_answer_sheet_step1`, `write_answer_sheet_step2`, `write_answer_sheet_step3`, `write_lookup_formulas`, `recalculate_with_libreoffice`

**Depends on**: evo-excel-data-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-excel-financial-formulas/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
