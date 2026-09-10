# Skill Creation Plan

**Task**: Write syzkaller syzlang descriptions (dev_ppdev.txt and dev_ppdev.txt.const) for the Linux parallel port driver (ppdev), covering all 28 ioctls, structs, flags, and constants for amd64/386 architectures.

**Rationale**: This task is a single coherent file-creation task: write two tightly coupled files (.txt syzlang descriptions and .txt.const constants) that must be perfectly synchronized. The background research document provides all needed information directly. Splitting into more skills would create artificial boundaries between inherently coupled concerns (e.g., ioctl descriptions depend on constant values). One skill covering the complete syzlang authoring pattern is sufficient.

**Number of skills**: 1

---

## Skill 1: evo-syzkaller-ppdev-description

**Description**: Creates complete syzkaller syzlang device driver descriptions for the Linux ppdev (parallel port) subsystem, including the .txt syscall/ioctl description file and the .txt.const architecture-specific constants file. Covers syz_open_dev pseudo-syscall, resource definitions, all 28 ppdev ioctls with correct argument directions, struct definitions, flag groups, and computed ioctl numbers for amd64 and 386.

**Responsibility**: Generate dev_ppdev.txt (syzlang descriptions with includes, resource, opener, ioctl variants, structs, flags) and dev_ppdev.txt.const (architecture-specific constant values) that pass syzkaller's make descriptions and make all verification steps.

**Key functions**: `generate_ppdev_syzlang_txt`, `generate_ppdev_const_file`, `compute_ioctl_number`, `validate_ioctl_directions`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-syzkaller-ppdev-description/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
