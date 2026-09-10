# Skill Creation Plan

**Task**: Simulate an open Dicke model steady state for 4 dissipation cases, compute cavity Wigner functions on 1000x1000 grids, and save as CSV files.

**Rationale**: The task has two distinct functional domains: (1) quantum physics simulation (building Hamiltonian, collapse operators, solving steady state, partial trace) and (2) Wigner function computation and CSV export. Separating these allows clean reuse and testing of the physics engine independently from the output pipeline.

**Number of skills**: 2

---

## Skill 1: evo-dicke-model-simulation

**Description**: Builds the open Dicke model Hamiltonian and Lindblad collapse operators in the full 2^N tensor product Hilbert space, solves for the steady-state density matrix, and extracts the reduced cavity state via partial trace. Supports all dissipation channels: cavity loss, local dephasing, local emission, local pumping, collective emission, and collective pumping.

**Responsibility**: Construct composite Hilbert space operators (cavity + N qubits), build the Dicke Hamiltonian, assemble collapse operator lists for arbitrary combinations of local and collective dissipation channels, solve for steady state using QuTiP's steadystate solver, and return the reduced cavity density matrix.

**Key functions**: `build_local_spin_op`, `build_collective_spin_ops`, `build_dicke_hamiltonian`, `build_collapse_operators`, `solve_steady_state`, `get_cavity_state`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-dicke-model-simulation/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-wigner-csv-export

**Description**: Computes the Wigner function of a bosonic density matrix on a specified phase-space grid using QuTiP and exports the result as a CSV file. Handles grid construction, method selection, and efficient pandas-based CSV writing.

**Responsibility**: Generate phase-space grid arrays, compute the Wigner function using qutip.wigner with the clenshaw method, and save the resulting 2D array to CSV with proper formatting using numpy savetxt or pandas DataFrame.

**Key functions**: `compute_wigner_function`, `save_wigner_to_csv`

**Depends on**: evo-dicke-model-simulation


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-wigner-csv-export/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
