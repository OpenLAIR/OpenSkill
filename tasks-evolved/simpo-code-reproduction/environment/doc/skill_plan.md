# Skill Creation Plan

**Task**: Implement the SimPO loss function in a trainer class and run a unit test to produce deterministic loss values saved to an npz file

**Rationale**: This is a focused task requiring implementing one function (simpo_loss) based on a well-documented formula, then running a test and saving results. The core knowledge is the SimPO loss math and its PyTorch implementation, plus environment setup. Two skills suffice: one for the loss implementation logic, one for environment/execution.

**Number of skills**: 2

---

## Skill 1: evo-simpo-loss-implementation

**Description**: Implements the SimPO loss function following the paper's mathematical formulation. Covers the exact formula: L = -logsigmoid(beta * (chosen_avg_logps - rejected_avg_logps) - gamma) with label smoothing support, plus reward computation for logging.

**Responsibility**: Provide the correct SimPO loss function implementation including: pi_logratios computation, gamma/beta margin factoring, F.logsigmoid-based loss with label smoothing, hinge loss variant, and detached reward returns. Handles sigmoid and hinge loss types.

**Key functions**: `simpo_loss`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-simpo-loss-implementation/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-simpo-environment-execution

**Description**: Handles environment setup (Python 3.10, PyTorch, required packages), running the unit test, and saving loss results to npz format with correct keys.

**Responsibility**: Set up the Python environment with correct dependencies (torch, numpy, transformers, etc.), execute the unit test script, ensure loss tensor is properly detached/converted and saved to /root/loss.npz with key 'losses', and log Python version info.

**Key functions**: `setup_environment`, `save_loss_to_npz`, `log_python_info`

**Depends on**: evo-simpo-loss-implementation


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-simpo-environment-execution/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
