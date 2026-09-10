import fitz
import re

def extract_page_text(page):
    """Get plain text from a PDF page."""
    return page.get_text("text")

def extract_words_with_positions(page):
    """Get words with bounding box coordinates.
    Returns list of tuples: (x0, y0, x1, y1, word, block_no, line_no, word_no)
    """
    return page.get_text("words")

def identify_author_block_region(page):
    """Find the author block area - typically in top portion of first page.
    Returns a fitz.Rect covering the author block area."""
    page_rect = page.rect
    # Author block is usually in top 35% of first page
    return fitz.Rect(0, 0, page_rect.width, page_rect.height * 0.35)

def detect_arxiv_identifiers(text):
    """Find arXiv IDs in text."""
    patterns = [
        r'arXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?',
        r'arXiv:\s*[a-z\-]+/\d{7}',
        r'\d{4}\.\d{4,5}(?:v\d+)?',  # bare arxiv id
    ]
    results = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            results.append(m.group())
    return list(set(results))

def detect_email_addresses(text):
    """Find email addresses in text."""
    pattern = r'[A-Za-z0-9\.\-+_]+@[A-Za-z0-9\.\-+_]+\.[A-Za-z]+'
    return list(set(re.findall(pattern, text)))

def detect_affiliations(text):
    """Find institutional affiliations."""
    keywords = ['University', 'Institute', 'Laboratories', 'Laboratory',
                'Dept.', 'Department', 'College', 'School of',
                'Community', 'Corporation', 'Inc.']
    lines = text.split('\n')
    affiliations = []
    for line in lines:
        line = line.strip()
        for kw in keywords:
            if kw in line and len(line) < 200:
                affiliations.append(line)
                break
    return list(set(affiliations))

def detect_venue_statements(text):
    """Find venue/conference acceptance statements."""
    patterns = [
        r'(?:Accepted|Published|To appear|Presented)\s+(?:at|in|for)\s+[A-Za-z0-9\s\-,]+',
        r'Interspeech\s+\d{4}',
        r'ICML\s+\w+',
        r'Proceedings\s+of\s+[^\n]+',
        r'\d+\.\d+/Interspeech\.\d{4}-\d+',  # DOI pattern
        r'ICML Workshop[^\n]*',
        r'Copyright\s+\d{4}\s+by\s+the\s+author',
    ]
    results = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            results.append(m.group().strip())
    return list(set(results))

def _extract_author_names_from_block(text, first_page_text):
    """Extract author names from the author block of a paper.
    Uses heuristics: names appear after title, before abstract, 
    contain capitalized words, often with superscript markers."""
    lines = first_page_text.split('\n')
    author_names = []
    
    # Find lines between title and abstract that look like author names
    in_author_section = False
    past_title = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Skip very first lines that are headers like "Preprint"
        if line.lower() in ['preprint', 'article', 'paper', 'draft']:
            continue
            
        # Detect abstract marker
        if line.lower().startswith('abstract') or line == 'Abstract':
            break
        
        # After title (usually first substantial line), look for author names
        # Author lines typically have commas, superscripts, or multiple capitalized words
        if past_title:
            # Check if this looks like an author line
            # Author lines have patterns like "Name1, Name2, Name3"
            # or contain superscript markers like *, 1, 2, etc.
            has_comma = ',' in line
            has_superscript = bool(re.search(r'[\*♠♣♦♥†‡§¶∗⋆]|\d+[,\s]', line))
            has_at = '@' in line
            
            # Extract individual names from author lines
            if has_comma or has_superscript or has_at:
                # Clean the line of superscript markers and affiliations
                cleaned = re.sub(r'[♠♣♦♥†‡§¶∗⋆]', '', line)
                cleaned = re.sub(r'\s*\d+\s*', ' ', cleaned)
                cleaned = re.sub(r'\*', '', cleaned)
                # Split by comma or 'and'
                parts = re.split(r',|\band\b', cleaned)
                for part in parts:
                    part = part.strip()
                    # A name typically has 2-4 capitalized words
                    words = part.split()
                    if 1 <= len(words) <= 5 and all(w[0].isupper() for w in words if len(w) > 1 and w[0].isalpha()):
                        # Filter out non-name words
                        skip_words = {'University', 'Institute', 'Department', 'Dept',
                                     'College', 'School', 'USA', 'China', 'UK', 'Japan',
                                     'Abstract', 'Introduction', 'Correspondence', 'Email'}
                        if not any(sw in part for sw in skip_words) and len(part) > 3:
                            author_names.append(part)
        
        # Heuristic: title is usually the first long line or the first few lines
        if not past_title and len(line) > 10:
            past_title = True
            # But don't count the title line itself as authors
            continue
    
    return author_names

def get_all_redaction_targets(pdf_path):
    """Main function: analyze a PDF and return all strings/patterns to redact.
    
    Returns dict with:
        - exact_strings: list of exact strings to redact
        - regex_patterns: list of regex pattern strings
        - link_patterns: list of URL substrings to match for link removal
    """
    doc = fitz.open(pdf_path)
    
    # Collect all text from first few pages
    all_text = ""
    first_page_text = ""
    for pg in range(min(3, len(doc))):
        page = doc[pg]
        text = extract_page_text(page)
        all_text += text + "\n"
        if pg == 0:
            first_page_text = text
    
    # Also get metadata
    metadata = doc.metadata
    
    exact_strings = []
    regex_patterns = []
    link_patterns = ['arxiv.org', '.edu', 'github.com', 'mailto:']
    
    # 1. Detect author names from metadata
    if metadata.get('author'):
        author_str = metadata['author']
        # Split by common separators
        for sep in [';', ',', ' and ']:
            if sep in author_str:
                names = [n.strip() for n in author_str.split(sep)]
                for name in names:
                    if name and len(name) > 2:
                        exact_strings.append(name)
                break
        else:
            if author_str.strip():
                exact_strings.append(author_str.strip())
    
    # 2. Detect emails
    emails = detect_email_addresses(all_text)
    exact_strings.extend(emails)
    
    # 3. Detect arXiv IDs
    arxiv_ids = detect_arxiv_identifiers(all_text)
    exact_strings.extend(arxiv_ids)
    
    # 4. Detect affiliations from first page
    affiliations = detect_affiliations(first_page_text)
    exact_strings.extend(affiliations)
    
    # 5. Detect venue statements
    venues = detect_venue_statements(all_text)
    exact_strings.extend(venues)
    
    # 6. Add standard regex patterns
    regex_patterns = [
        r'arXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?',
        r'arXiv:\s*[a-z\-]+/\d{7}',
        r'[A-Za-z0-9\.\-+_]+@[A-Za-z0-9\.\-+_]+\.[A-Za-z]+',
    ]
    
    # 7. Collect all links for analysis
    all_links = []
    for pg in range(len(doc)):
        page = doc[pg]
        links = page.get_links()
        for link in links:
            uri = link.get('uri', '')
            if uri:
                all_links.append(uri)
                # Extract GitHub usernames from URLs
                gh_match = re.search(r'github\.com/([^/]+)', uri)
                if gh_match:
                    username = gh_match.group(1)
                    if username not in ['espnet', 'MrYxJ']:  # skip common repos
                        exact_strings.append(username)
                        link_patterns.append(username)
    
    doc.close()
    
    # Deduplicate
    exact_strings = list(set(s for s in exact_strings if s and len(s) > 1))
    regex_patterns = list(set(regex_patterns))
    link_patterns = list(set(link_patterns))
    
    return {
        'exact_strings': exact_strings,
        'regex_patterns': regex_patterns,
        'link_patterns': link_patterns,
        'metadata': metadata,
    }
