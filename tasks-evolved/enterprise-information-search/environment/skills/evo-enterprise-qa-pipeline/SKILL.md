---
name: evo-enterprise-qa-pipeline
description: Orchestrates the end-to-end question-answering pipeline for enterprise Slack data. Parses malformed question.txt files, searches extracted document text for answers (employee IDs, URLs, team member names), tracks token consumption, and writes the final answer.json output.
---

# evo-enterprise-qa-pipeline

End-to-end QA pipeline for enterprise Slack conversation data.

## Key Functions

- `parse_question_file(filepath)` - Parse malformed/unquoted JSON question file using YAML trick
- `extract_employee_ids(text)` - Extract employee IDs matching eid_XXXXXXXX pattern
- `extract_urls(text)` - Extract HTTP/HTTPS URLs from text
- `search_context_for_answer(messages, keywords, context_window)` - Search Slack messages for relevant context
- `find_report_authors_and_reviewers(product_data, report_name)` - Find who authored and reviewed a report
- `find_competitor_insight_providers(product_data, insight_type)` - Find who discussed competitor strengths/weaknesses
- `find_competitor_demo_urls(product_data)` - Find demo URLs for competitor products
- `count_tokens_for_text(text)` - Count tokens using tiktoken cl100k_base encoding
- `run_qa_pipeline(data_dir, question_file, output_file)` - Run full pipeline
- `write_answer_json(answers, output_file)` - Write structured JSON output

## Usage

```python
import sys
sys.path.insert(0, "/app/environment/skills/evo-enterprise-qa-pipeline/scripts")
from utils import run_qa_pipeline

run_qa_pipeline("/root/DATA", "/root/question.txt", "/root/answer.json")
```

## Depends On

- evo-enterprise-doc-parser (for document extraction utilities)
