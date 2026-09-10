# Skill Creation Plan

**Task**: Read problem.json, execute 5 JAX computation tasks (row mean, element-wise square, logistic loss gradient, RNN scan, JIT MLP), and save outputs as .npy files.

**Rationale**: The task involves a straightforward pipeline: load data, compute with JAX, save results. All 5 problems share the same I/O pattern but differ in JAX computation. A two-skill decomposition separates data I/O concerns from the JAX computation logic, keeping the solution clean without over-decomposing.

**Number of skills**: 2

---

## Skill 1: evo-jax-io

**Description**: Handles loading problem.json, reading .npy/.npz input files into JAX arrays, and saving JAX array results back to .npy files with proper numpy conversion.

**Responsibility**: All file I/O: parsing problem.json, loading numpy/npz data files and converting to JAX arrays, and safely serializing JAX arrays to .npy output files using np.asarray().

**Key functions**: `load_problem_json`, `load_input_data`, `save_jax_array`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-jax-io/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-jax-compute

**Description**: Implements all five JAX computation tasks: row-wise mean reduction, element-wise squaring, logistic loss gradient via jax.grad, RNN forward pass via jax.lax.scan, and JIT-compiled 2-layer MLP forward pass.

**Responsibility**: All JAX computation logic for the five problem tasks, dispatching by problem ID and returning JAX arrays as results.

**Key functions**: `compute_basic_reduce`, `compute_map_square`, `compute_grad_logistic`, `compute_scan_rnn`, `compute_jit_mlp`, `dispatch_task`

**Depends on**: evo-jax-io


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-jax-compute/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
