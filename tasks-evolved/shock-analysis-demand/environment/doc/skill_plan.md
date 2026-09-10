# Skill Creation Plan

**Task**: Estimate an investment spending shock to Georgia's economy using demand-side macro accounting in Excel, collecting IMF WEO and GeoStat SUT data, computing import content share, and modeling 3 scenarios with bell-shaped spending allocation.

**Rationale**: This task has three distinct functional domains: (1) data ingestion and population from pre-downloaded IMF WEO and GeoStat SUT sources into Excel sheets, (2) computing the import content share from Supply and Use Tables, and (3) building the demand-side National Accounts shock model with scenario analysis. These map cleanly to the three steps in the task instruction and have clear data flow dependencies.

**Number of skills**: 3

---

## Skill 1: evo-macro-weo-data

**Description**: Populates the WEO_Data sheet in the Excel workbook with IMF World Economic Outlook data for Georgia, and extends projections (real GDP growth held constant from 2027-2043, GDP deflator extended using 4-year average growth rate). Also copies GeoStat Supply and Use Table sheets into the workbook.

**Responsibility**: Reading pre-downloaded IMF WEO data files and GeoStat SUT files from /root/data/, populating the WEO_Data sheet with the correct WEO subject codes (NGDP, NGDPD, NGDP_R, NGDP_D, NGDP_RPCH, PCPIPCH), extending GDP deflator and real GDP projections to 2043 using Excel formulas, and copying the 38x38 SUPPLY and USE sheets into the workbook.

**Key functions**: `populate_weo_data`, `extend_deflator_projection`, `extend_real_gdp_projection`, `copy_sut_sheets`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-weo-data/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-macro-sut-import-share

**Description**: Links Supply and Use Table data to the SUT Calc sheet, computes product-level import shares using the proportionality assumption, and calculates the estimated import content share of investment (cell C46).

**Responsibility**: Populating columns C-H of the SUT Calc sheet by linking data from the copied SUPPLY and USE sheets, computing import-to-supply ratios per product, applying them to GFCF column, and deriving the aggregate import content share theta using Excel formulas.

**Key functions**: `link_sut_to_calc_sheet`, `compute_import_shares`, `calculate_import_content_share`

**Depends on**: evo-macro-weo-data


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-sut-import-share/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-macro-demand-shock-scenarios

**Description**: Builds the National Accounts (NA) sheet with the full demand-side investment shock model including bell-shaped spending allocation, currency conversion, deflation, import leakage adjustment, and multiplier application. Creates 3 scenario tables with different parameters.

**Responsibility**: Linking WEO baseline data to NA sheet columns C and J, setting assumptions (exchange rate 2.746, demand multiplier 0.8, bell-shape allocation percentages), implementing the full formula chain (USD allocation → GEL conversion → real deflation → import adjustment → multiplier → GDP impact %), and replicating the structure for Scenario 2 (multiplier=1.0) and Scenario 3 (import share=0.5).

**Key functions**: `setup_na_assumptions`, `build_bell_shape_allocation`, `build_shock_formula_chain`, `create_scenario_tables`, `recalculate_workbook`

**Depends on**: evo-macro-weo-data, evo-macro-sut-import-share


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-macro-demand-shock-scenarios/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
