# Skill Creation Plan

**Task**: Run GLM to simulate Lake Mendota vertical water temperature (2009-2015) with RMSE < 2°C against field observations.

**Rationale**: Single cohesive workflow: configure namelist, execute GLM, parse NetCDF, compare to observations, and iterate calibration. One skill keeps these tightly-coupled steps together with shared utilities.

**Number of skills**: 1

---

## Skill 1: evo-glm-simulation

**Description**: Utility skill for running General Lake Model (GLM) simulations: edit glm3.nml namelist parameters, execute the GLM binary, parse NetCDF output with dynamic Lagrangian layers, match to field observations, compute RMSE, and iteratively calibrate key parameters (Kw, wind_factor, coef_mix_hyp, lw_factor, ch) to achieve RMSE < 2°C.

**Responsibility**: End-to-end GLM workflow: namelist I/O, subprocess execution, NetCDF parsing with depth conversion (lake_depth - z), observation matching/interpolation, RMSE computation, and calibration loop.

**Key functions**: `run_glm`, `update_glm_nml`, `read_glm_nml`, `verify_bcs`, `process_glm_netcdf`, `load_field_observations`, `calculate_rmse`, `calibrate_parameters`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-glm-simulation/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
