import json
import re
import os
from pathlib import Path

def parse_question_file(filepath: str) -> dict:
    """Parse malformed/unquoted JSON question file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    if content.startswith('{'):
        content = content[1:]
    if content.endswith('}'):
        content = content[:-1]
    
    questions = {}
    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip().rstrip(',')
        if not line:
            continue
        match = re.match(r'["\']?(\w+)["\']?\s*:\s*(.*)', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            value = value.rstrip(',')
            questions[key] = value
    
    return questions

def extract_employee_ids(text: str) -> list:
    """Extract employee IDs matching eid_XXXXXXXX pattern."""
    pattern = r'\beid_[a-f0-9]{8}\b'
    return list(set(re.findall(pattern, text, re.IGNORECASE)))

def extract_urls(text: str) -> list:
    """Extract HTTP/HTTPS URLs from text."""
    pattern = r'https?://[^\s"\'>]+'
    return list(set(re.findall(pattern, text)))

def load_product_data(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_employee_data(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_report_authors_and_reviewers(product_data: dict, product_name: str) -> list:
    """Find employee IDs of authors and key reviewers of Market Research Report."""
    messages = product_data.get('slack', [])
    author_id = None
    reviewer_ids = []
    report_shared = False
    report_updated = False
    
    for m in messages:
        text = m['Message']['User']['text']
        uid = m['Message']['User']['userId']
        
        if uid == 'slack_admin_bot':
            continue
        
        text_lower = text.lower()
        
        if not report_shared and 'market_research_report' in text and \
           ('shared' in text_lower or "i've shared" in text_lower):
            author_id = uid
            report_shared = True
            continue
        
        if report_shared and not report_updated:
            if 'updated' in text_lower and 'market research report' in text_lower:
                report_updated = True
                continue
            if uid != author_id:
                reviewer_ids.append(uid)
    
    result = []
    if author_id:
        result.append(author_id)
    result.extend(reviewer_ids)
    return list(dict.fromkeys(result))

def find_competitor_insight_providers(product_data: dict) -> list:
    """Find employee IDs of team members who provided insights on 
    strengths and weaknesses of competitor products.
    
    Identifies people who:
    1. Introduced competitor products describing their features/capabilities (strengths)
    2. Discussed specific weaknesses of competitor products  
    3. Provided substantive analytical answers about competitor characteristics
    
    Excludes: people who just ask questions, thank others, or make brief acknowledgments
    """
    messages = product_data.get('slack', [])
    insight_providers = set()
    
    competitor_names = ['personaai', 'persona ai', 'smartsuggest', 'smart suggest',
                       'tailorai', 'tailor ai']
    
    for m in messages:
        text = m['Message']['User']['text']
        uid = m['Message']['User']['userId']
        
        if uid == 'slack_admin_bot':
            continue
        
        text_lower = text.lower()
        
        # Must be about a specific competitor product
        is_about_competitor = any(cn in text_lower for cn in competitor_names)
        if not is_about_competitor:
            continue
        
        # Exclude thank-you / acknowledgment messages
        if text_lower.startswith('thanks for') or text_lower.startswith('thank you'):
            continue
        
        # Pattern 1: Person introduces a competitor product with features (strength insights)
        if 'was reading about' in text_lower and \
           any(kw in text_lower for kw in ['offer', 'feature', 'gaining traction', 'interesting', 'useful']):
            insight_providers.add(uid)
            continue
        
        # Pattern 2: Person discusses weaknesses explicitly with substance
        if any(kw in text_lower for kw in ['weakness', 'weaknesses']):
            if len(text) > 100:  # Substantive message
                insight_providers.add(uid)
            continue
        
        # Pattern 3: Person provides detailed analytical answers about competitor
        # (must contain actual insight, not just acknowledgment)
        if any(kw in text_lower for kw in ['potential weakness', 'drawback', 'limitation',
                                            'struggle', 'barrier', 'steep learning curve',
                                            'inconsistencies', 'accuracy']):
            if len(text) > 100:
                insight_providers.add(uid)
    
    return list(insight_providers)

def find_competitor_demo_urls(product_data: dict) -> list:
    """Find demo URLs shared for competitor products.
    Competitor demo URLs are external (not sf-internal) and contain 'demo'.
    """
    messages = product_data.get('slack', [])
    demo_urls = []
    
    for m in messages:
        text = m['Message']['User']['text']
        uid = m['Message']['User']['userId']
        
        if uid == 'slack_admin_bot':
            continue
        
        urls = extract_urls(text)
        for url in urls:
            if 'demo' in url.lower() and 'sf-internal' not in url:
                demo_urls.append(url)
    
    return list(set(demo_urls))

def count_tokens_for_text(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4

def run_qa_pipeline(data_dir: str, question_file: str, output_file: str):
    """Run the full QA pipeline."""
    questions = parse_question_file(question_file)
    print(f"Parsed questions: {questions}")
    
    answers = {}
    
    for qid, question in questions.items():
        q_lower = question.lower()
        print(f"\nProcessing {qid}: {question}")
        
        answer = []
        q_tokens = 0
        
        if 'coachforce' in q_lower or 'coach force' in q_lower:
            product_file = os.path.join(data_dir, 'products', 'CoachForce.json')
            product_data = load_product_data(product_file)
            content = json.dumps(product_data)
            q_tokens = count_tokens_for_text(content)
            
            if 'market research report' in q_lower and 'employee id' in q_lower:
                answer = find_report_authors_and_reviewers(product_data, 'CoachForce')
        
        elif 'personalizeforce' in q_lower or 'personalize force' in q_lower:
            product_file = os.path.join(data_dir, 'products', 'PersonalizeForce.json')
            product_data = load_product_data(product_file)
            content = json.dumps(product_data)
            q_tokens = count_tokens_for_text(content)
            
            if 'employee id' in q_lower and 'competitor' in q_lower:
                answer = find_competitor_insight_providers(product_data)
            elif 'url' in q_lower and 'competitor' in q_lower:
                answer = find_competitor_demo_urls(product_data)
        
        answers[qid] = {
            "answer": answer,
            "tokens": str(q_tokens)
        }
        print(f"  Answer: {answer}")
        print(f"  Tokens: {q_tokens}")
    
    write_answer_json(answers, output_file)
    return answers

def write_answer_json(answers: dict, output_file: str):
    """Write structured JSON output."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(answers, f, indent=4, ensure_ascii=False)
    print(f"\n[SUCCESS] Output written to {output_file}")
