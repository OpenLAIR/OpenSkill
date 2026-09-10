# Domain Reference for evo-meeting-request-parser

**Responsibility**: Extract meeting dates/date ranges, time availability windows, meeting duration, and timezone from free-text email bodies. Returns structured data ready for calendar querying.

**Key functions to implement**: parse_meeting_request, extract_dates, extract_time_window, extract_duration_minutes, normalize_to_datetime_ranges

---

## 4. Date and Time Formatting in Python


Date formatting is highly critical for string-matching, Natural Language Processing (NLP), and correct API interactions.

## 5. JSON I/O Pattern


Integrating the utility into a broader automation architecture (like an agentic framework) typically requires strict file I/O operations.

**Pattern Specification:**
When reading `test_input.json` for operations and writing to `results.json`, it is confirmed that the API responds with `id` representing the message identifier [cite: 1, 27]. However, the external architecture expects `messageId` per the query parameter specifications. The adapter logic translates this.

```python
import json

def process_email_tasks(input_file='test_input.json', output_file='results.json'):
    with open(input_file, 'r') as f:
        tasks = json.load(f)
        
    results = {"sent_results": []}
    
    for task in tasks.get("emails_to_send", []):
        payload = create_raw_message(task['to'], task['sender'], task['subject'], task['body'])
        # service is assumed to be instantiated previously
        msg_id, thread_id = send_email(gmail_service, payload)
        
        # Writing 'messageId' to match schema expectations, extracted from response['id']
        results["sent_results"].append({
            "messageId": msg_id, # Confirmed: response['id'] Maps to messageId concept [cite: 1]
            "threadId": thread_id,
            "status": "Success" if msg_id else "Failed"
        })
        
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
```

---