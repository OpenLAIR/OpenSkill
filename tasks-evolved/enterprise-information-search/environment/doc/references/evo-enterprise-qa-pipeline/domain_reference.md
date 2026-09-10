# Domain Reference for evo-enterprise-qa-pipeline

**Responsibility**: Parsing malformed/unquoted JSON questions, mapping questions to search strategies (regex for employee IDs and URLs, keyword/context-based search for names), aggregating answers across multiple documents, token counting, and writing structured JSON output.

**Key functions to implement**: parse_question_file, extract_employee_ids, extract_urls, search_context_for_answer, count_tokens_for_text, run_qa_pipeline, write_answer_json

---

## 4. Text Search and Information Extraction Patterns


With raw text successfully extracted, we apply Natural Language Processing (NLP) heuristics and Regular Expressions to satisfy search requests.

### 4.1 Keyword and Regex Extraction

Extracting structured attributes relies heavily on the `re` module. To match case-insensitive text, `re.IGNORECASE` must be applied.

*   **Employee IDs**: Patterns typically consist of a prefix followed by digits (e.g., `EMP001`, `E-12345`). Regex: `r'\bE(?:MP)?-?\d{3,5}\b'`
*   **URLs**: Web addresses follow consistent protocol schemes. Using `re.findall(r'(https?://[^\s]+)', text)` successfully captures links [cite: 36], though handling optional trailing punctuation requires advanced capturing groups [cite: 37].

```python
import re

class InformationExtractor:
    def __init__(self, document_text: str):
        self.text = document_text
        
    def find_keywords(self, keywords: list) -> dict:
        """
        Searches for specific keywords case-insensitively.
        """
        results = {}
        for kw in keywords:
            # Using regex \b for word boundaries to avoid partial matches
            pattern = re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
            matches = pattern.findall(self.text)
            results[kw] = len(matches)
        return results
        
    def extract_employee_ids(self) -> list:
        """
        Extracts IDs matching EMP001 or E-12345.
        """
        pattern = r'\bE(?:MP)?-?\d{3,5}\b'
        return list(set(re.findall(pattern, self.text, re.IGNORECASE)))
        
    def extract_urls(self) -> list:
        """
        Extracts HTTP/HTTPS URLs from the text.
        """
        pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s"\'<>]*'
        return list(set(re.findall(pattern, self.text)))
```

### 4.2 Fuzzy String Matching

Exact keyword matching fails in the presence of OCR errors, typos, or slight linguistic variations (e.g., "Market Reserch Report"). Fuzzy string matching algorithmically calculates the Levenshtein distance—the minimum number of single-character edits required to change one word into the other [cite: 38].

Historically, `FuzzyWuzzy` was the dominant library in Python [cite: 38, 39]. However, modern text processing heavily favors `RapidFuzz` [cite: 38, 40]. RapidFuzz is written in C++, operates up to 40% faster, uses less memory, and provides an MIT license (compared to FuzzyWuzzy's restrictive GPL license) [cite: 38, 39, 41]. RapidFuzz's API mirrors FuzzyWuzzy's, making migration effortless (`from rapidfuzz import fuzz`) [cite: 39].

```python
from rapidfuzz import fuzz

def fuzzy_search_document(text: str, query: str, threshold: float = 80.0) -> bool:
    """
    Checks if a query exists in the text using sliding window fuzzy matching.
    """
    # Token set ratio handles words out of order and partial strings
    score = fuzz.token_set_ratio(query.lower(), text.lower())
    return score >= threshold
```

## 5. Question-Answering Pipeline for Enterprise Documents


Enterprise skill modules often map user queries (stored in configurations or files) to programmatic tasks. A significant challenge arises when input configurations contain malformed JSON (e.g., missing double quotes around keys or string values), typical of hand-edited files or JSONP outputs [cite: 42].

### 5.1 Parsing Unquoted JSON

Python's standard `json.loads()` requires strictly formatted JSON strings [cite: 42, 43]. If keys are unquoted (e.g., `{question: what is the company name?}`), `json` fails with a `JSONDecodeError` [cite: 44].

There are three primary strategies to handle this:
1.  **Regex Injection**: Using `re.sub` to dynamically inject quotes around keys [cite: 45, 46]. This is fragile and prone to edge-case failures.
2.  **HJSON / ChompJS**: Utilizing third-party libraries like `hjson` or `chompjs` designed specifically to ingest sloppy JavaScript objects [cite: 42, 43].
3.  **The YAML Trick**: YAML is a superset of JSON. The PyYAML parser (`yaml.safe_load`) gracefully handles unquoted keys and values, mapping them to a Python dictionary natively [cite: 46, 47, 48]. *Note: YAML requires a space after the colon* [cite: 42, 47].

Using the PyYAML approach is robust and minimizes exotic dependencies [cite: 46, 48].

```python
import yaml
import json

def parse_sloppy_json(filepath: Path) -> dict:
    """
    Parses a malformed/unquoted JSON file into a Python dictionary using YAML.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Ensure there's a space after colons to satisfy YAML requirements
        import re
        content_spaced = re.sub(r':(?=[^\s])', ': ', content)
        
        parsed_dict = yaml.safe_load(content_spaced)
        return parsed_dict
    except Exception as e:
        print(f"[ERROR] Failed to parse sloppy JSON: {e}")
        return {}
```

### 5.2 Mapping Questions to Search Strategies

Once the configuration is parsed, queries must map to analytical functions.

```python
def map_question_to_strategy(question: str, extractor: InformationExtractor) -> dict:
    q_lower = question.lower()
    
    if "employee id" in q_lower:
        return {"type": "Regex Extraction", "result": extractor.extract_employee_ids()}
    elif "url" in q_lower or "link" in q_lower:
        return {"type": "Regex Extraction", "result": extractor.extract_urls()}
    else:
        # Default to fuzzy search against common enterprise entities
        entities = ["Market Research Report", "CoachForce", "PersonalizeForce", 
                    "competitor", "author", "key reviewer"]
        found = []
        for entity in entities:
            if fuzzy_search_document(extractor.text, entity, threshold=85):
                found.append(entity)
        return {"type": "Fuzzy Search", "result": found}
```

## 6. Token Counting Patterns


In systems that eventually feed text to Large Language Models (LLMs), calculating the number of tokens consumed by the context window is critical for managing context limits and API costs [cite: 49, 50]. 

When operating entirely offline or avoiding unnecessary API calls, OpenAI's `tiktoken` library provides an ultra-fast BPE (Byte Pair Encoding) tokenizer [cite: 49]. The encoding `cl100k_base` corresponds to modern models like GPT-4 and GPT-3.5-turbo [cite: 50, 51]. For optimal memory and CPU performance when tokenizing massive strings (e.g., 10MB+ text dumps), using the undocumented `encode_to_numpy()` method prevents the library from allocating an enormous Python list, dramatically reducing memory spikes [cite: 52].

```python
import tiktoken

class TokenTracker:
    def __init__(self, model_name: str = "gpt-4"):
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        self.total_tokens = 0
        
    def count_tokens(self, text: str) -> int:
        """
        Counts tokens efficiently. Uses standard encode for short strings.
        For large-scale enterprise data, could use len(encoding.encode_to_numpy(text)).
        """
        if not text:
            return 0
        tokens = len(self.encoding.encode(text))
        self.total_tokens += tokens
        return tokens
        
    def get_report(self) -> dict:
        return {
            "total_tokens_consumed": self.total_tokens,
            "cost_estimate_usd_gpt4o": (self.total_tokens / 1_000_000) * 5.00 # Assuming $5/1M tokens
        }
```

## 7. Output Formatting and Execution Assembly


The final stage in the module wraps the extracted metadata, answers, and token usage into a cleanly formatted, valid JSON file. This guarantees interoperability with downstream systems via `json.load()` [cite: 43, 48].

```python
def write_json_output(data: dict, output_path: Path):
    """
    Serializes a Python dictionary to a well-formatted JSON file.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"[SUCCESS] Output written to {output_path}")
    except Exception as e:
        print(f"[ERROR] Failed to write JSON output: {e}")