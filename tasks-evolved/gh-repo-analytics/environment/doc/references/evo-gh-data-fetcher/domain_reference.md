# Domain Reference for evo-gh-data-fetcher

**Responsibility**: Execute gh CLI commands to retrieve PR and issue data with proper flags (--search, --state, --json, --limit), parse JSON output, and return structured Python lists of dictionaries.

**Key functions to implement**: fetch_prs, fetch_issues, run_gh_command, parse_gh_timestamp

---

## 1. The `gh` CLI Commands for Listing and Filtering


The GitHub CLI provides the `gh pr list` and `gh issue list` commands, which serve as the primary conduits for retrieving repository objects [cite: 1, 2]. By default, these commands output human-readable, formatted text. For programmatic data extraction, the interface relies heavily on a combination of filtering flags (`--search`, `--state`) and structured output formatting (`--json`).

## 2. Filtering Merged vs. Closed PRs


The lifecycle states of Pull Requests are conceptually more complex than standard issues. An issue is a binary: open or closed. A Pull Request is a ternary: open, closed (abandoned/rejected), or merged (accepted).

## 3. Date and Time Parsing in Python


Handling time-series data accurately is essential for computing metrics like Time-to-Merge (TTM) or Cycle Time.

## 4. Label Filtering for Bug Issues


Issue and PR tracking relies heavily on labels. Identifying "bug" reports is a standard metric extraction requirement.

## 5. `gh` CLI Search Qualifiers


Understanding GitHub's search qualifiers allows you to push filtering logic to the server side, minimizing the amount of data transferred and processed by Python.

## 6. Python Subprocess Patterns for Calling `gh`


Integrating the `gh` CLI via Python requires leveraging the `subprocess` module. The goal is to execute the command securely, capture standard output (STDOUT) while intercepting standard error (STDERR), and parse the output into native Python dictionaries.

## 7. Common Pitfalls and Operational Considerations


While the `gh` CLI drastically simplifies data extraction, a variety of architectural and logical pitfalls can skew metrics or break automation pipelines.