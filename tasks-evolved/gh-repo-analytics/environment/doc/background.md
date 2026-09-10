# Comprehensive Analysis of GitHub CLI (`gh`) API Integration via Python for Repository Data Extraction

**Key Points:**
*   The GitHub CLI (`gh`) offers structured JSON output (`--json`), serving as a powerful, high-level alternative to writing custom REST or GraphQL queries.
*   Data truncation is a significant risk: queries utilizing the `--search` flag divert to the GitHub Search API, which enforces a strict maximum limit of 1000 results regardless of the `--limit` specified.
*   Timestamps are returned in ISO 8601 format with a UTC `Z` suffix. Native parsing in Python requires version 3.11 or later, or manual string manipulation for backward compatibility. 
*   Pull Request states cleanly differentiate among `OPEN`, `CLOSED`, and `MERGED` natively in the JSON payload, eliminating the ambiguity present in standard issue tracking.
*   Python `subprocess` integration requires careful handling of character encoding, stdout capturing, and standard error checks to build a resilient data pipeline.

**Introduction**
As data-driven engineering management becomes standard practice, the need to extract, process, and analyze software development lifecycle metrics is increasingly paramount. Platforms such as GitHub hold immense amounts of metadata regarding pull requests (PRs), issues, and developer collaboration. While direct interaction with the GitHub REST or GraphQL APIs is common, the GitHub CLI (`gh`) provides an incredibly potent, authenticated, and flexible abstraction layer. By combining the `gh` CLI with Python's system execution capabilities, data scientists and engineering managers can build highly reusable, scriptable utility functions. This report exhaustively details the methodology, syntax, edge cases, and best practices for querying repository data within specific date ranges using Python and `gh`.

**Context and Complexity**
Integrating external command-line interfaces into Python applications introduces complexities related to process management, standard output parsing, and API rate limitations. Furthermore, GitHub's underlying architecture routes different `gh` commands to either its GraphQL backend or its Elasticsearch-powered Search API depending on the arguments provided. This routing dictates pagination limits and field availability. Consequently, creating a "simple wrapper" requires an intimate understanding of both the CLI's argument parsers and the intricacies of Python's `subprocess` and `datetime` libraries.

## 1. The `gh` CLI Commands for Listing and Filtering

The GitHub CLI provides the `gh pr list` and `gh issue list` commands, which serve as the primary conduits for retrieving repository objects [cite: 1, 2]. By default, these commands output human-readable, formatted text. For programmatic data extraction, the interface relies heavily on a combination of filtering flags (`--search`, `--state`) and structured output formatting (`--json`).

### 1.1 Exact Syntax and Date Range Filtering
To target a specific repository like `cli/cli` and filter by a date range, the `--repo` (or `-R`) and `--search` flags are utilized [cite: 1, 2]. The exact syntax to retrieve PRs created in December 2024 is as follows:

```bash
gh pr list --repo cli/cli --search "created:2024-12-01..2024-12-31"
```

For issues, the syntax is identical:

```bash
gh issue list --repo cli/cli --search "created:2024-12-01..2024-12-31"
```

The `--search` flag accepts standard GitHub advanced search qualifiers [cite: 3]. The date range syntax `YYYY-MM-DD..YYYY-MM-DD` is inclusive.

### 1.2 The `--limit` Flag and Pagination Behavior
By default, both `gh pr list` and `gh issue list` return a maximum of 30 items [cite: 2, 4]. To request more, the `--limit` flag is utilized. However, a critical architectural constraint emerges when combining the `--limit` flag with the `--search` flag or certain filters like `--label`. 

When standard list flags are used, `gh` uses the GraphQL API to paginate through records. But when `--search` or specific labels are introduced, `gh` dynamically switches to querying the GitHub Search API [cite: 5]. The GitHub Search API enforces a hard ceiling: it will never return more than 1000 results for any single query, regardless of pagination [cite: 5, 6]. 

**What happens if you set `--limit 2000`?**
If the query relies on the Search API, the CLI will fetch up to 1000 items and then silently truncate the remaining results, sometimes issuing a standard error warning [cite: 5, 7]. It will not throw a critical failure, which means data pipelines can unknowingly drop data.

**How to ensure ALL results are retrieved:**
To bypass the 1000-item maximum, you must implement **date-chunking** in your Python script. Instead of querying a whole year, you programmatically break the date range into smaller intervals (e.g., weekly or daily intervals like `created:2024-12-01..2024-12-07`) ensuring that no single query exceeds the 1000-item threshold.

### 1.3 Utilizing the `--state` Flag
The `--state` flag dictates the lifecycle status of the objects being retrieved.
For `gh pr list`, the accepted values are `open`, `closed`, `merged`, and `all` [cite: 1, 4].
For `gh issue list`, the accepted values are `open`, `closed`, and `all` (since issues cannot be merged) [cite: 2].

If the `--state` flag is omitted, the CLI defaults to `open` [cite: 2, 4].

### 1.4 Structured JSON Output (`--json`)
The most crucial flag for Python integration is `--json`. This flag instructs the CLI to bypass terminal UI rendering and emit raw, structured JSON [cite: 8]. You must specify a comma-separated list of the exact fields you wish to retrieve.

Available and requested field mappings:
| Requested Data | Exact `--json` Field Name | Data Type in JSON |
| :--- | :--- | :--- |
| Creation Date | `createdAt` | String (ISO 8601) |
| Merge Date (PRs) | `mergedAt` | String (ISO 8601) or null |
| Closure Date | `closedAt` | String (ISO 8601) or null |
| Lifecycle State | `state` | String (`OPEN`, `CLOSED`, `MERGED`) |
| Author Login | `author` | Object (`{"login": "...", ...}`) |
| Labels | `labels` | Array of Objects (`[{"name": "bug"}]`) |
| ID/Number | `number` | Integer |

To query all these fields for PRs, the command becomes:
```bash
gh pr list --repo cli/cli --search "created:2024-12-01..2024-12-31" --state all --json number,state,createdAt,mergedAt,closedAt,author,labels
```

### 1.5 Interaction Between `--search` and `--state`
A common pitfall is the interaction between `--search` and `--state`. The `--search` flag passes raw strings to the GitHub search engine, while `--state` modifies the baseline query. 
If you execute `gh pr list --state closed --search "state:open"`, the query criteria will conflict. The CLI will often prioritize the `--search` qualifier, or the API will attempt to find a PR that is simultaneously open and closed, returning zero results [cite: 9, 10]. 
**Gotcha:** It is highly recommended to control the state either *exclusively* through the `--state` flag or *exclusively* inside the `--search` string (`is:merged`, `is:open`). When building robust utilities, using `--state all` combined with specific search qualifiers is the safest programmatic approach to avoid CLI-level overrides.

## 2. Filtering Merged vs. Closed PRs

The lifecycle states of Pull Requests are conceptually more complex than standard issues. An issue is a binary: open or closed. A Pull Request is a ternary: open, closed (abandoned/rejected), or merged (accepted).

### 2.1 Exact String Values in JSON
When utilizing `--json state`, the output relies on GitHub's GraphQL schema, which represents enumerations as uppercase strings. Therefore, the exact string values returned for the `state` field are `OPEN`, `CLOSED`, and `MERGED` [cite: 1, 11].

### 2.2 Distinguishing Merged vs. Closed
Historically, GitHub's REST API returned PRs merely as `open` or `closed`, requiring developers to check the boolean `merged` field or `merged_at` timestamp [cite: 11, 12]. However, because `gh` leverages the newer API layers, `state: "MERGED"` is an explicit, separate state from `state: "CLOSED"`.
*   `"state": "MERGED"` implies the PR's code was successfully integrated into the base branch [cite: 13].
*   `"state": "CLOSED"` implies the PR was rejected, abandoned, or closed without integrating the code [cite: 13].

### 2.3 The Behavior of `--state all`
When you query `gh pr list --state all`, the CLI retrieves items across all three states: `OPEN`, `CLOSED`, and `MERGED` [cite: 4, 14]. You do not need a separate query to fetch merged PRs if you use `--state all`. You can subsequently separate them in Python by checking the `state` key in the parsed JSON dictionaries.

## 3. Date and Time Parsing in Python

Handling time-series data accurately is essential for computing metrics like Time-to-Merge (TTM) or Cycle Time.

### 3.1 Format of Timestamps
The fields `createdAt`, `mergedAt`, and `closedAt` are returned as UTC timestamps formatted according to the ISO 8601 standard, specifically conforming to RFC 3339 [cite: 15, 16]. 
Example: `"2024-12-15T10:30:00Z"`
The `Z` at the end stands for "Zulu time," which represents UTC (+00:00) [cite: 15, 17].

### 3.2 Python `datetime` Parsing and Version Behaviors
Parsing ISO 8601 strings featuring the `Z` suffix has historically been a point of friction in Python's standard library.
*   **Python 3.10 and earlier**: The `datetime.fromisoformat()` method strictly supported formats outputted by `datetime.isoformat()`. It did **not** support the trailing `Z` [cite: 17, 18]. Attempting to parse `2024-12-15T10:30:00Z` in Python 3.10 results in a `ValueError` [cite: 18].
*   **Python 3.11, 3.12, and later**: A major update to `datetime.fromisoformat()` allowed it to parse standard ISO 8601 strings, gracefully accepting and interpreting the `Z` suffix as UTC [cite: 17, 19, 20].

### 3.3 The Safe Portable Approach
If building a reusable utility that must operate across various Python environments (e.g., Python 3.9 through 3.12), you cannot rely safely on `datetime.fromisoformat()` directly parsing the `Z`. 

The most robust, version-agnostic approach is string replacement prior to parsing, replacing `Z` with `+00:00`:
```python
from datetime import datetime, timezone

def parse_gh_timestamp(ts_string: str) -> datetime | None:
    if not ts_string:
        return None
    # Replace 'Z' with explicit UTC offset '+00:00' for pre-3.11 compatibility
    safe_string = ts_string.replace("Z", "+00:00")
    return datetime.fromisoformat(safe_string)
```
Alternatively, utilizing `datetime.strptime(ts_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)` is portable but strictly assumes the string will always end in `Z` and lacks fractional second support. The `.replace("Z", "+00:00")` methodology is generally preferred.

## 4. Label Filtering for Bug Issues

Issue and PR tracking relies heavily on labels. Identifying "bug" reports is a standard metric extraction requirement.

### 4.1 JSON Structure for Labels
When querying with `--json labels`, the `gh` CLI returns an array of label objects, not an array of flat strings. The precise schema looks like this:
```json
[
  {
    "id": "MDU6TGFiZWwyMDgwNDU5NDY=",
    "name": "bug",
    "description": "Something isn't working",
    "color": "d73a4a"
  },
  {
    "name": "high priority",
    ...
  }
]
```
To access the label text, you must iterate over the list and extract the `name` key [cite: 8, 21].

### 4.2 Python Filtering Logic
To check if any label contains the substring "bug", string normalization is critical. Label names on GitHub are technically case-sensitive at creation but functionally treated as case-insensitive in search. A Python utility should implement case-insensitive substring matching:

```python
def is_bug_issue(issue_data: dict) -> bool:
    labels = issue_data.get("labels", [])
    for label in labels:
        label_name = label.get("name", "").lower()
        if "bug" in label_name:
            return True
    return False
```

## 5. `gh` CLI Search Qualifiers

Understanding GitHub's search qualifiers allows you to push filtering logic to the server side, minimizing the amount of data transferred and processed by Python.

### 5.1 Syntax for Date Ranges
The exact syntax for filtering by creation date uses the `created:` qualifier [cite: 3].
Syntax: `created:2024-12-01..2024-12-31`
It is important to note that the dates used in `created:` and other time-based search qualifiers are interpreted by GitHub in **UTC** [cite: 15, 22]. If your local time zone is dramatically different, an issue submitted late on December 31st local time might be registered as January 1st UTC, thereby missing the filter window.

### 5.2 Combining Search Qualifiers
You can aggressively chain qualifiers inside the `--search` argument.
For example:
```bash
gh issue list --repo cli/cli --search "created:2024-12-01..2024-12-31 label:bug"
```
This is a perfectly valid and correct command [cite: 10]. It instructs the server to only return issues created in December 2024 that also contain the exact label "bug". This is much more efficient than fetching all issues and filtering for bugs in Python.

### 5.3 Filtering by Closed Date
If you want to track burn-down rates or issue resolution velocity, you might want to find issues *closed* during a specific date range, regardless of when they were created. GitHub provides the `closed:` search qualifier for this exact purpose [cite: 3, 23].
```bash
gh issue list --repo cli/cli --search "closed:2024-12-01..2024-12-31" --state closed
```
Similarly, for pull requests, the `merged:` qualifier can be utilized to locate PRs merged within a specific window (`merged:2024-12-01..2024-12-31`) [cite: 23].

## 6. Python Subprocess Patterns for Calling `gh`

Integrating the `gh` CLI via Python requires leveraging the `subprocess` module. The goal is to execute the command securely, capture standard output (STDOUT) while intercepting standard error (STDERR), and parse the output into native Python dictionaries.

### 6.1 Best Practices using `subprocess.run()`
The recommended pattern utilizes `subprocess.run` with the arguments passed as a list of strings rather than a single concatenated string. This avoids shell injection vulnerabilities and parsing errors associated with whitespace handling.

```python
import subprocess
import json

def run_gh_command(repo: str, query: str, state: str, limit: int, fields: list) -> list:
    command = [
        "gh", "pr", "list",
        "--repo", repo,
        "--search", query,
        "--state", state,
        "--limit", str(limit),
        "--json", ",".join(fields)
    ]
    
    try:
        # capture_output=True captures stdout and stderr. 
        # text=True decodes bytes to strings using the default encoding.
        # check=True raises a CalledProcessError if exit code != 0
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # Parse the JSON output
        return json.loads(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing gh CLI: {e}")
        print(f"STDERR: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON output: {e}")
        return []
```

### 6.2 Parsing and Error Handling
Because `gh` outputs strict JSON when the `--json` flag is supplied [cite: 8], `json.loads(result.stdout)` operates deterministically. However, there are two distinct failure modes to catch:
1.  **Process Failure (`subprocess.CalledProcessError`)**: This occurs if `gh` encounters a network error, missing authentication, or an invalid repository. The CLI will return a non-zero exit code, and details will be located in `e.stderr`.
2.  **Serialization Failure (`json.JSONDecodeError`)**: If the CLI encounters an internal error or the API goes down mid-stream, it might emit plaintext error logs to STDOUT instead of valid JSON. Wrapping the `json.loads` call prevents the Python application from crashing.

## 7. Common Pitfalls and Operational Considerations

While the `gh` CLI drastically simplifies data extraction, a variety of architectural and logical pitfalls can skew metrics or break automation pipelines.

### 7.1 Search and State Conflicts
As detailed in section 1.5, passing conflicting directives to `--search` (e.g., `is:open`) and `--state` (e.g., `closed`) results in GitHub returning an empty dataset [cite: 9, 10]. Ensure logical coherence.

### 7.2 API Limits vs CLI Limits
Understanding the 1000-item maximum is critical [cite: 5, 6]. If your Python function requests `--limit 5000` alongside `--search`, `gh` limits the response to 1000 without warning. If you need 5000 PRs, your Python script must divide the request into sequential calls spanning smaller date blocks, appending the results to a centralized list.

### 7.3 `closedAt` vs. `mergedAt` Mechanics
When a Pull Request is merged, its state transitions to `MERGED` [cite: 1, 11]. Simultaneously, the `mergedAt` timestamp is populated. Crucially, the `closedAt` timestamp is **also** populated, representing the moment the PR was removed from the "open" queue (by merging) [cite: 24, 25]. 

If you are computing metrics and count all PRs where `closedAt` is not null as "rejected/abandoned", you will erroneously double-count merged PRs. 
**Avoidance strategy:** Always evaluate the `state` field.
*   If `state == 'MERGED'`, treat it as merged.
*   If `state == 'CLOSED'`, treat it as closed/abandoned without merging.

### 7.4 Authentication Permissions (`GH_TOKEN`)
The `gh` CLI requires an authentication token to operate reliably against the API. This is supplied via the `GH_TOKEN` environment variable [cite: 26, 27]. 
For querying **public repositories** (like `cli/cli`), a standard Personal Access Token (classic) with the `public_repo` scope is sufficient [cite: 28]. For fine-grained tokens, read-only access to "Public Repositories" is required [cite: 29]. Without a token, GitHub strictly limits rate requests (often 60 per hour based on IP), causing rapid pipeline failure. With a token, the rate limit expands to 5000 requests per hour for the REST API and analogous node limits for GraphQL.

### 7.5 Rate Limiting Considerations
Making sequential subprocess calls invokes multiple API requests. While `gh` handles individual backoff inherently well, firing thousands of parallel `subprocess.run` calls can trigger GitHub's secondary rate limits (abuse mechanisms). A synchronous, iterative loop is recommended over multithreading when dealing with high-volume CLI scraping.

---

## 8. Working End-to-End Python Code Example

The following comprehensive Python script illustrates how to encapsulate the aforementioned theory into reusable, robust utility functions. The script fetches PRs and issues for `cli/cli`, handles ISO 8601 parsing securely, computes Time-to-Merge (TTM), and identifies the most prolific PR author.

```python
import subprocess
import json
import os
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict, Any

# Ensure we have required fields for extraction
PR_FIELDS = ["number", "state", "createdAt", "mergedAt", "closedAt", "author", "labels"]
ISSUE_FIELDS = ["number", "state", "createdAt", "closedAt", "author", "labels"]

def parse_iso8601(date_str: str) -> datetime | None:
    """
    Parses a GitHub ISO 8601 timestamp safely across Python versions.
    Replaces the UTC 'Z' indicator with '+00:00' to support Python < 3.11.
    """
    if not date_str:
        return None
    try:
        safe_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(safe_str)
    except ValueError as e:
        print(f"Error parsing date {date_str}: {e}")
        return None

def fetch_github_data(entity: str, repo: str, date_range: str, limit: int, fields: List[str], state: str = "all") -> List[Dict[str, Any]]:
    """
    Executes the gh CLI to fetch either 'pr' or 'issue' data.
    """
    # Defensive check on limit due to GitHub Search API constraints
    if limit > 1000:
        print("Warning: GitHub Search API caps results at 1000. Limit will be restricted.")
        limit = 1000
        
    search_query = f"created:{date_range}"
    
    command = [
        "gh", entity, "list",
        "--repo", repo,
        "--search", search_query,
        "--state", state,
        "--limit", str(limit),
        "--json", ",".join(fields)
    ]
    
    print(f"Executing: {' '.join(command)}")
    
    try:
        # Run process, capture stdout and stderr, ensure failure raises exception
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        print(f"Successfully retrieved {len(data)} {entity}(s).")
        return data
        
    except subprocess.CalledProcessError as e:
        print(f"CLI Error! Exit code: {e.returncode}")
        print(f"STDERR: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error: {e}")
        return []

def analyze_prs(prs: List[Dict[str, Any]]) -> None:
    """
    Analyzes Pull Requests to calculate Average Time to Merge and top authors.
    """
    if not prs:
        print("No PR data to analyze.")
        return

    merged_prs = []
    author_counts = Counter()

    for pr in prs:
        # 1. Author Aggregation
        author_data = pr.get("author")
        if author_data and isinstance(author_data, dict):
            author_login = author_data.get("login")
            if author_login:
                author_counts[author_login] += 1

        # 2. Time to Merge Calculation
        # Distinguish MERGED explicitly to avoid counting CLOSED (abandoned) PRs
        state = pr.get("state")
        if state == "MERGED":
            created_ts = parse_iso8601(pr.get("createdAt"))
            merged_ts = parse_iso8601(pr.get("mergedAt"))
            
            if created_ts and merged_ts:
                # Time delta in days
                time_to_merge_days = (merged_ts - created_ts).total_seconds() / (24 * 3600)
                merged_prs.append(time_to_merge_days)

    # Output PR Metrics
    print("\n--- Pull Request Metrics ---")
    if merged_prs:
        # LaTeX Equivalent Math: \mu = \frac{1}{N} \sum_{i=1}^{N} (t_{merge} - t_{create})
        avg_ttm = sum(merged_prs) / len(merged_prs)
        print(f"Total Merged PRs analyzed: {len(merged_prs)}")
        print(f"Average Time-to-Merge: {avg_ttm:.2f} days")
    else:
        print("No merged PRs found in the dataset.")

    if author_counts:
        top_author, count = author_counts.most_common(1)
        print(f"Most prolific PR author: {top_author} ({count} PRs)")

def extract_bug_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters issues to return only those containing a 'bug' label.
    """
    bug_issues = []
    for issue in issues:
        labels = issue.get("labels", [])
        # Iterate through the label schema [{"name": "..."}]
        for label in labels:
            name = label.get("name", "").lower()
            if "bug" in name:
                bug_issues.append(issue)
                break  # Prevent duplicate addition if multiple bug-related labels exist
    return bug_issues

if __name__ == "__main__":
    # Ensure GH_TOKEN is set for API authentication and rate limit prevention
    if not os.environ.get("GH_TOKEN"):
        print("Notice: GH_TOKEN environment variable is not set. You may hit rate limits.")
    
    target_repo = "cli/cli"
    date_window = "2024-12-01..2024-12-31"
    
    # 1. Fetch and Analyze Pull Requests
    print("\n--- Fetching Pull Requests ---")
    pr_data = fetch_github_data(
        entity="pr", 
        repo=target_repo, 
        date_range=date_window, 
        limit=500, 
        fields=PR_FIELDS, 
        state="all"
    )
    analyze_prs(pr_data)
    
    # 2. Fetch Issues and Filter by Label
    print("\n--- Fetching Issues ---")
    issue_data = fetch_github_data(
        entity="issue", 
        repo=target_repo, 
        date_range=date_window, 
        limit=500, 
        fields=ISSUE_FIELDS, 
        state="all"
    )
    
    bug_issues = extract_bug_issues(issue_data)
    print("\n--- Issue Metrics ---")
    print(f"Total Issues Found: {len(issue_data)}")
    print(f"Issues tagged as bugs: {len(bug_issues)}")
```

### Conclusion
By meticulously controlling pagination limitations, handling the schema shifts between `CLOSED` and `MERGED` states, and utilizing robust, version-compatible Python `datetime` extraction logic, engineering teams can build resilient metrics pipelines. The approach mapped above shields the application from hidden data loss caused by API constraints and ensures accurate representation of development lifecycle metrics using the `gh` API.

**Sources:**
1. [archlinux.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEUsx7tlKsAoLxaFa2X2TPA-yEL93yMcSW-pCdDX5BXDdFN10pvF0nOKqVjybA27B7Z06l592TrYI4DRVa-QxgX-W1wjCYQj87b7d_nw7QU13hiIHNGqBUpCwKXo13Tv0eWvw==)
2. [archlinux.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFg1ewF8-ZaG8ehe_z8LiJHazSlkdCdvS1ssV8RnRzEIyc27dQGL8Bl-SFyiMgndiaP1hdR1RVyhCqMZAqOiQEHo7h_7l0q2cTtd2RaBS8us8aMwR8sULyb51I6N8ZiLtAZ_gB-w3r0JUixLneXn68BOm5vZJ1O)
3. [traviswimer.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7buS-45GZgo0LlP4CrkoWGmeimwR7wOOyMoGo1GTs8owJgny956vQe-FyVHItjjQubaH9DCycyauNUjtKoGtm5jhQHZaScDFeq4ZMVJVvop5gbYCXjDYiMoAl5YZLFzPe57U_7IhQqR2G)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyOVgKyXiPB0mvE8YUVttjTXm_K_kmLHPlJZdMfN8CBROD6J9blrDmd0l2Jj_CwjYGE1ay5MX3gPnlM5ttnQ_Vxa7UhpEkBi5w5HSNKRJdihwz1eyQR_hkxIzow5I=)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVpz-w8mdwjZVyNWiPQGZcy5U2bQrYGg3xq67mlnIpFbq8D5y4u-fDxwQBcBXSahIZCmXLJAmiiu9OPTAQlBmSDVBlpq1CXGrYAxSsO9WHET0Jo48deieG2cwl)
6. [devactivity.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEoU7iw2wGwJSlDEqLKDMf-Ax2wldFKERKkIP6mqFxr6M2-zCEgboP6xwzVsoSbbfSX5Ad4s14nWctpu88Qx84pz-DzyFHees7Iz47ruA-tLR8kmLhqlu9xLhvT7uGJz93AIhwMjVnCyXa9jWt-JKhre3HdLm4qyWhxL4FvpcvoSwVDxg6JLf-1WpmtfVu1kU-iMvyJazXB21LKAabmnmNM8MivHj5l)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVTo4yE5AwjcqlL7J8Ax184Urc4Bk8rqz5d3Z2bhUnRArFL_LYJNmiMc5p1G163cMCgM5rh3KgXDc0YSc6D2OQFFpWB14rC-Z-R7ee6APgP8NdzpOY3hsv2Chy7QkB2ug=)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYBV2m-BtDF_4Ut67RqqwHNe9-lMdiZurvGxlPBerdRGCtiAHectnIr68v3JNZJmhyRR_sp1glf_6HQsz0CmxeVpD2mhzU-lgmweCOpCJrT2zzZrH3nOg8UM3bDVLVqf3ciNHAUg==)
9. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgQEj9NFqfyv8wof0ksv0WR6Hxc6af0k7dX-o2hDg-dLDK6BWUjCL_sljC5X8kU7JZZ3yQK8W9qMzIQ-wDwZ6QDTmofwgv8uMZE33Dh4gg4ttvE76LodWtAUyhg8OMLpYCrih6Owx39Jeh888-0qHhvtK6JQ==)
10. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEKdkN5UEjupMJ1APCz_ZP-joaiVtawduwTh6VQ2arnK-kRX-wIBQNL5OhZXNc0M0q679YBCSB-kl13A7nxXvTwAv86SWUsiPzpRUAC0Uft4Hl_iYU-Izey7HqpxvZLlYiN4hMBoOhQ9b0x2HDYM0rEU2tygnXSly_pj6uEfnaj_U_eYCwI)
11. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGkH5Ov7rM2s10h2jVDfrPolo31sxxj4KWYdcN_yQxZeHB1LoKy8EztjxsFerRTrJqWvdtMGYBxEi5XNecpkMxYHHzpbnjkUKlG97ytCfsw-CE7kV15fuJ_FeE=)
12. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFzXdUYuDQ3Tedbp748tZZGhbtiuBjVzkKN-7UXlnbqAfdiWUR8CAQC8BnUlwz_bAWD_KiKs7AlUJOpqbZJgcuGrDmg5EdrHsuXPMgYiUwb4a0Q67Kn6q-0PaAPtDwgsCZarqdkt8IQRVkremaGEjclajPdEx4C8FMntJ7zYHjz5KVFsgDINxWsq7fEnepq3JvDXwpuO-grAmaNCchH2uBEsRY-N3DtwnKQcYDs)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGM6yuVE_8cVMZ1i9O-0CP3pSUJpTSQhmr3YyV8fXkSI3WE8lFrYYbhHOJWiey4qvJrCGpGMqoUic-vrG_HpV4r5I16Rxei8oknaimALtPfaZo34IqEjOXFtRP5diXmQop9O4IXj2Jl33zYxhVwfoGiwOjbd9GN_UIC8UIwCk1yG3t0zgk8qTkDT2Hk8YJp5886t9eTqBngbXz_fmEgB4xa2e8=)
14. [freekb.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVDdhCBJrXuF7sfP4geXJ9f157rpAthweBtUvPKLutBLpGg2UluMH4P0ZOhn32XwU9CNaG6BGXI9Ph0sTGSOAq70Slx2ej21d73XNE58AGS1CJsux_TazMy9RA)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdAYcIgNJV88ydiRh3uX3YBztbSL99AACeEvhnw9W2jIcnvBp3Lz88AxFmHjmxqJzlGlIXNUN6W4_SDYUvBMgifI094RCiaElEwgCUiHPTYcH94Mq5uWdSe5j0JVlp9brhnKYPXIfHuQvxKGsALA_qL7OkmngHo3oZWUALIYvaKrizaUIKK6bUY5Vo6I06ldSDpE5Y0zQgmJzvDgxm_w5bkVBiKBlW27g=)
16. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEK_3dQSkYi5nL5ITGQBEP3rn60oViH7TMhhgxn-s-jVKcqG9AyeOqlq-72thKBrsz9SwcbJHIUavia1QNkaPumVsNPFTllpYwutDUobWmIMY5JmqS4VjaHVOOTnWq1lZE2C1qOJkuwoZ4C)
17. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHF7JTl1OjDvCWegFSSp6uPUpV8lHSFxaYYQ2h6BgYeOQp6qpzEpVejvjQmKVEDMPHbMfrr6gybUd0jhuw3QBoMl-FAIVYGteKwoXsW9rOfyB2Kt-1tYv-WDsCLXr6fPibnB7kipqj33pNVe-DE6TMc2grq3-Vg7UZN6dXExT5payF-RrIiUE15UMtyMo8bj9Rt)
18. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEHe5PiyUUdH9lhzitw232Y-rOeS7ZGxLG6AVdvczWJUb3yqiBuzByQdlR93pFnERXt_y4L8tev8Znra0b3sIqEBKzs2Id89se-SgQ8YjkcB0_2QADoej9dwQw-Eq-jLzvY8QAD5Z0-QNBRgOeuGkwieNcRZb4=)
19. [python.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOwQ8m7vupSF-6klz6KwIsI9QxhoY3opcjGF71InbRMn1B4VTqA040FNXL2GvUD1uGCFpGctUsmVABAHh3JQ-RkjRVQyTBzyWZKNRrJo6U0vAkELcECfuTNHHRC5OYmOeA)
20. [nkmk.me](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFpr_Z53mzr5FGSz6IwwjgFCUI6HGOUM10ZyV1FFLdxEHU4EzYNuF-WXrc4wcQ67n0RF9jT7kH3qV_8QxZAs0Lm7wJp-c-QtNWVEOEFYSHz5_aMVebbmtQz3ze9kBNbYoSMmaAWXbrGT_nJkNPgiZ490j7G0bc=)
21. [smithery.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0yuxTWgktIEaDOP7UZB4UNMGGIq_eGHo8TAt1iDymPVHyjXX10qe6FWHpota_y_xcdX1NKBbiLk2PRud87LwCZrl82ReN00FteRWGb_GigKaWJfhJ_32L7roPgtTgmVfk8NBAi9u1SW3P5dA_mFX_)
22. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcI1wMfBG31XJtBmXY6YWeEe6RVRVrWRcWaOMiFx9uS9JxNI4nD076QNF_Iz4wCVbMofab2668pFjCj4dRRdplNKdgfpZ0mgubl1d11_49K1YmtGHSecVuNgT-X-tU95cKq-PZ3ZZTd3mCLVBNuQ==)
23. [libraries.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFop9KctUKV8VvtM5woybObPHAo-c35GBezUIKSQAcLa57TvtpZxqlDbBD9sDv5sSO034Dd8cOSNWudIQpQEIl5s-wYHAdS_9oyL_RlRoIFF38UUWupyo-gXybUU8TNudPyQ7VJiA==)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFyuxSE-7kT1z13GrQbshSlBdZq5BkhonGV6D_8bRLE1h95PEtdSbL6FMOPHloS_aHDIumTNIppKXE8N57iJYiZGRZQ-JvqpsxEMc88HNT9Tb764sKHZncTzgj2H8mZflzbiRmNXnirXqxH_8zl457yCLoz2c6r1imErBVOEZx_A4gXTzhLCErm03eLUW2-oTQgbzjEz5i5XPkKKIepJgHbbk7ZdOI10GiP)
25. [github.blog](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZEfVXkNstFIWEreQr9Pbn-50sWQvajQV7K9qtFhR7PrCL1Jx1dlXIaql81rUwBSWcXH3mY7r5dDbIv8JIvJgQMGCKA2I345K9Lml6fycyatWmMIc2fDL3-zvcTLMUhKk2g4kaeeMipKDu2hYa_D64ikkXLHdv1LfwmKTz_TPWYx3AzZ9F2_Ya52cNHUGHhY_YUqjhAzeAMHUrhfVp-5771t8zHZ7edmHpjDQV0M8doG_7BN3HzFfH)
26. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGmVsXnvIWHQDBue4qsby1_5ub3-0m_XaOWRPl_tSdtgsUKR6L9ADSEuqqFOPPoRvfwI0-NrZj1-Xjtxz8QVos2YXGJgbeqmW7tThsLXRXA4DV1gVd26xwhMscqQw4xEH4=)
27. [micheal.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHM4j82eagAgp3TCS6URDCOjdAukHWYLtQJnVtlwK2ewFmrqvdHkFQp-GZHfC7L_QEdILWg7QcmKVEiy2EAQRn2RgpFN8p7x45vmJfklX9D49Y0BO1DLyVh8oDdkDH3T6xyYIp6xKgfVkeoNx1qTjE70It2OHtt7yoH32LKMHm4)
28. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpNGm4Ni4JhtiZ1wg5Tkrig4VnqQWe5HjUTgQ7tzW4MjXpIiEI-0PNuj-fJYAlljNi1yw78bbhZ3-OHArlq5fG5cM_OkiKXvFz4tmE5EtIzjl8Mb9swGogRein)
29. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmSnrEA6d2X3NA4IWESpeuj71pMtEiG0mSpq4_Qm7N4nuFtiZDBCdJcVqmSUcqYxPcnHdxjprvEDnf0K5Wcw2baBUmx_nOyDgigH07N7A8nHwXp3rjopphL2lLm24TWtYdTczLB-zNOwmPOkZi3V96wrJJEggFsPBxLOa7ONrKfeNwflQqWfLaRwROLVR0reBDSB9ErMZdeHx691LB_KOkjT3WUpLBJWU=)
