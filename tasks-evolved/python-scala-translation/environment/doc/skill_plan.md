# Skill Creation Plan

**Task**: Translate a Python tokenizer module (Tokenizer.py) to idiomatic Scala 2.13, preserving all classes, functions, and behavior while following Scala conventions.

**Rationale**: The translation task involves three distinct concerns: (1) understanding the Python source structure and mapping its constructs to Scala idioms, (2) handling Scala-specific type system patterns (ADTs, generics, variance, error handling), and (3) producing compilable, well-structured Scala code with proper naming conventions and standard library usage. These are tightly coupled enough to warrant 2 skills: one for Python-to-Scala pattern mapping and one for the actual code generation.

**Number of skills**: 2

---

## Skill 1: evo-scala-idiom-mapping

**Description**: Maps Python language constructs to idiomatic Scala 2.13 equivalents. Covers enum-to-sealed-trait ADTs, dataclass-to-case-class, ABC-to-trait, Protocol-to-trait, generic type variables with variance, Union types, Optional/Option, error handling (Try/Either/Option), naming convention conversion (snake_case to camelCase), collections mapping, datetime/BigDecimal handling, and companion object patterns.

**Responsibility**: Provide reference mappings and utility functions for converting Python constructs (enums, dataclasses, ABCs, protocols, generics, type variables, overloads, generators, comprehensions, exceptions, naming conventions) to their idiomatic Scala 2.13 equivalents.

**Key functions**: `snake_to_camel`, `map_python_type_to_scala`, `map_enum_to_sealed_trait`, `map_dataclass_to_case_class`, `map_abc_to_trait`, `map_protocol_to_trait`, `map_collection_type`, `map_error_handling_pattern`, `map_generic_variance`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-scala-idiom-mapping/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-scala-tokenizer-generator

**Description**: Generates the complete Scala 2.13 Tokenizer.scala file by translating all Python classes (TokenType, Token, BaseTokenizer, StringTokenizer, NumericTokenizer, TemporalTokenizer, UniversalTokenizer, WhitespaceTokenizer, TokenizerBuilder) and functions (tokenize, tokenizeBatch, toToken, withMetadata) using idiomatic Scala patterns including sealed traits, case classes, companion objects, Option/Try/Either error handling, and functional builder patterns.

**Responsibility**: Produce the final compilable Scala 2.13 source file at /root/Tokenizer.scala with correct package structure, all required classes/traits/objects, proper imports, JSON handling via standard library, and method implementations that match Python behavior.

**Key functions**: `generate_token_type_adt`, `generate_token_case_class`, `generate_base_tokenizer_trait`, `generate_specialized_tokenizers`, `generate_tokenizer_builder`, `generate_top_level_functions`, `generate_json_serialization`, `assemble_scala_file`

**Depends on**: evo-scala-idiom-mapping


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-scala-tokenizer-generator/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
