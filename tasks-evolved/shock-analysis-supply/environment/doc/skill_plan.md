# Skill Creation Plan

**Task**: Estimate investment spending shock impact on Georgia's potential GDP using Cobb-Douglas production function, HP filter, and perpetual inventory method in Excel via openpyxl and LibreOffice

**Rationale**: The task has three distinct concerns: (1) collecting and populating data from multiple online sources into the spreadsheet, (2) building the Excel model with formulas for HP filter, production function, and investment shock calculations, and (3) running LibreOffice Solver to optimize the HP filter. These map to data acquisition, formula construction, and solver execution.

**Number of skills**: 3

---

## Skill 1: evo-macro-data-acquisition

**Description**: Handles downloading and parsing macroeconomic data from PWT, IMF WEO, and ECB SDW databases for Georgia, and populating the corresponding sheets in the Excel workbook

**Responsibility**: Download PWT Excel file and extract rnna, emp, labsh, hc for Georgia; scrape/download IMF WEO real GDP level (NGDP_R) and growth rate (NGDP_RPCH) for 2000-2027; download ECB CFC data for Georgia; populate sheets PWT, WEO_Data, and CFC data in test-supply.xlsx

**Key functions**: `download_pwt_data`, `extract_pwt_georgia_variables`, `fetch_imf_weo_data`, `fetch_ecb_cfc_data`, `populate_data_sheets`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-data-acquisition/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-macro-excel-formulas

**Description**: Constructs all Excel formulas for depreciation rate calculation, Cobb-Douglas production function, HP filter setup, capital stock projection, TREND extrapolation, and investment shock modeling using openpyxl

**Responsibility**: Write Excel formulas in sheets Production, WEO_Data, CFC data, and Investment for: depreciation rate from CFC/K, LnK/LnY/LnZ calculations, HP filter objective function and second-order differences, average depreciation rate, K/Y ratio anchoring, TREND function for extending LnZ, Ystar_base and Ystar_with calculations, deltaK and K_With from investment shock, and all linking formulas between sheets

**Key functions**: `build_depreciation_formulas`, `build_hp_filter_formulas`, `build_production_function_formulas`, `build_capital_projection_formulas`, `build_investment_shock_formulas`, `link_cross_sheet_references`

**Depends on**: evo-macro-data-acquisition


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-excel-formulas/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-macro-solver-execution

**Description**: Executes LibreOffice Calc Solver programmatically to minimize the HP filter objective function, or alternatively implements a Python-based HP filter optimization and writes results back to the spreadsheet

**Responsibility**: Run the HP filter optimization either via LibreOffice UNO Solver API or scipy.optimize to find smoothed LnZ trend values that minimize the HP filter objective with lambda=6.25; recalculate all formulas via LibreOffice headless mode; save final results to test-supply.xlsx

**Key functions**: `run_libreoffice_solver`, `run_scipy_hp_filter`, `recalculate_workbook`, `write_solver_results`

**Depends on**: evo-macro-excel-formulas


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-solver-execution/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
