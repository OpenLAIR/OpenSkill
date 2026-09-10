# Domain Reference for evo-gh-report-generator

**Responsibility**: Process fetched PR/issue data to compute all required metrics (total/merged/closed PRs, avg merge days, top contributor, total issues, bug count, resolved bugs) and serialize results to /app/report.json.

**Key functions to implement**: compute_pr_metrics, compute_issue_metrics, identify_top_contributor, generate_report

---

## 2. Filtering Merged vs. Closed PRs


The lifecycle states of Pull Requests are conceptually more complex than standard issues. An issue is a binary: open or closed. A Pull Request is a ternary: open, closed (abandoned/rejected), or merged (accepted).

## 3. Date and Time Parsing in Python


Handling time-series data accurately is essential for computing metrics like Time-to-Merge (TTM) or Cycle Time.

## 4. Label Filtering for Bug Issues


Issue and PR tracking relies heavily on labels. Identifying "bug" reports is a standard metric extraction requirement.

## 8. Working End-to-End Python Code Example


The following comprehensive Python script illustrates how to encapsulate the aforementioned theory into reusable, robust utility functions. The script fetches PRs and issues for `cli/cli`, handles ISO 8601 parsing securely, computes Time-to-Merge (TTM), and identifies the most prolific PR author.

```python
import subprocess
import json
import os
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict, Any