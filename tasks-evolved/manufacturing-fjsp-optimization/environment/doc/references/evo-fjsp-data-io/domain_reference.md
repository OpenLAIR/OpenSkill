# Domain Reference for evo-fjsp-data-io

**Responsibility**: All file I/O: reading instance definitions, downtime windows, policy budgets, baseline schedules; writing solution.json and schedule.csv with proper type handling (numpy int64 serialization).

**Key functions to implement**: parse_fjsp_instance, parse_downtimes_csv, parse_policy_budgets, parse_baseline_schedule, export_solution_json, export_solution_csv

---

## 2. Input Data Parsing Patterns


Data engineering and parsing form the bedrock of scheduling algorithms. We must extract information from standardized text files, CSVs, and JSON files [cite: 11].

## 7. Output Formatting


Interoperability in modern tech stacks requires outputting results in strictly formatted JSON and CSV files. A major pitfall in pure-Python processing when combining with numerical data (like Pandas or NumPy) is that JSON cannot natively serialize `numpy.int64` objects.

## 8. Common Pitfalls and Solutions


When developing FJSP algorithms from scratch, developers frequently encounter specific logic and data bugs:

1. **0-based vs 1-based Indexing:**
   Benchmark instance text files traditionally represent jobs, operations, and machines starting at index 1 [cite: 9, 10]. Python arrays naturally start at 0. Failing to subtract `1` from machine IDs during parsing will cause `IndexError` exceptions during execution. All internal algorithms should strictly use 0-based indexing, and formatting to 1-based indexing should occur only during UI rendering or logging.

2. **Unsorted Downtime Windows:**
   The `find_earliest_start` function fundamentally relies on processing intervals from earliest to latest. Passing an unsorted list of downtime windows will cause the interval-merging step to fail, leading to algorithms incorrectly identifying overlaps as free gaps. **Always `sort()` downtimes by start time upon parsing [cite: 15].**

3. **Varying Processing Times (Flexible vs Classical JSP):**
   In standard JSP, an operation's duration is fixed. In FJSP, it changes based on the selected machine [cite: 11, 22]. A common pitfall is caching the processing time at the *operation* level rather than reading it from the `eligible_machines` dictionary during the active machine selection phase.

4. **Ignoring Downtimes During Local Search Moves:**
   A simple swapping mechanism in a Simulated Annealing algorithm (e.g., swapping two operations on the same machine) might place an operation directly over a downtime window. If the algorithm updates start/end times via a naive addition without routing through `find_earliest_start`, the schedule immediately becomes structurally infeasible [cite: 21].

5. **Serialization Errors (`TypeError: Object of type int64 is not JSON serializable`):**
   If parsing inputs via Pandas (e.g., reading baseline schedules or downtimes), integer fields are automatically converted to `numpy.int64`. The standard Python `json.dump()` crashes on this type. Applying the custom `NpEncoder` shown above completely resolves this issue.

---