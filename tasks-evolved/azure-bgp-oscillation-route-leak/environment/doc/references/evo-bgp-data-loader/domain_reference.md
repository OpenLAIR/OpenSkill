# Domain Reference for evo-bgp-data-loader

**Responsibility**: Load all input JSON files (route.json, preferences.json, local_pref.json, relationships.json, topology.json, route_events.json, possible_solutions.json) and normalize data types, especially converting string dictionary keys back to integers for ASN lookups.

**Key functions to implement**: load_json_with_int_keys, load_json_list, load_all_bgp_data

---

## 5. Data Loading Patterns and Data Pipeline



### 5.1 JSON File Loading from a Fixed Path


Building a robust data pipeline in Python requires defensively loading JSON files from disk, typically from a predefined directory such as `/app/data/`. Key best practices include:
1. **Using Context Managers**: Always use `with open(...)` to ensure file descriptors are reliably closed.
2. **Explicit Encoding**: Always specify `encoding='utf-8'` to prevent cross-platform text decoding errors.
3. **Graceful Error Handling**: Catch `FileNotFoundError` and `json.JSONDecodeError` to prevent pipeline crashes.

### 5.2 Handling Integer Keys in Python JSON (The Pitfall)


The most significant pitfall when processing topological graph data in Python via JSON is the serialization of dictionary keys. According to the JSON specification (RFC 8259), object keys must be strings [cite: 17, 18]. When Python uses `json.dump()` to serialize a dictionary like `{65002: {"prefer_via": 65003}}`, the integer key `65002` is silently coerced into the string `"65002"`. 

When reading this back using `json.load()`, Python yields `{"65002": {"prefer_via": 65003}}` [cite: 18, 19]. This causes critical `KeyError` failures when the code subsequently tries to look up the integer ASNs found elsewhere in the data pipeline.

To mitigate this, one must intercept the JSON decoding process using the `object_hook` parameter in `json.load()` to cast numeric string keys back to integers [cite: 20].

```python
import json
import os

def load_json_with_int_keys(filepath: str) -> dict:
    """
    Loads a JSON file, converting string keys that represent integers back to Python int types.
    """
    def convert_keys(obj):
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                # Attempt to cast key to integer
                try:
                    new_key = int(k)
                except ValueError:
                    new_key = k
                new_dict[new_key] = v
            return new_dict
        return obj

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Using object_hook executes the function on every decoded dictionary
            return json.load(f, object_hook=convert_keys)
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {filepath}")
        return {}
```

---