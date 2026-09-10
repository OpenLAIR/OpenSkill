"""
evo-citation-scorer utility functions.
Scores citation matches and classifies as real or fake.
"""
import string
import json
import re
from difflib import SequenceMatcher


def normalize_string(text):
    """Normalize a string for comparison: lowercase, remove punctuation, articles."""
    if not text:
        return ""
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    for article in [' a ', ' an ', ' the ']:
        text = text.replace(article, ' ')
    return ' '.join(text.split())


def calculate_title_similarity(title1, title2):
    """
    Calculate similarity between two titles using token-based matching.
    Returns a score from 0 to 100.
    """
    norm1 = normalize_string(title1)
    norm2 = normalize_string(title2)
    
    if not norm1 or not norm2:
        return 0
    
    # Direct sequence matching
    direct_score = SequenceMatcher(None, norm1, norm2).ratio() * 100
    
    # Token sort: sort words and compare
    sorted1 = ' '.join(sorted(norm1.split()))
    sorted2 = ' '.join(sorted(norm2.split()))
    token_sort_score = SequenceMatcher(None, sorted1, sorted2).ratio() * 100
    
    return max(direct_score, token_sort_score)


def check_author_overlap(bib_author_str, api_authors_list):
    """
    Check if there's any author overlap between BibTeX author string and API authors.
    Returns (has_overlap: bool, overlap_count: int)
    """
    bib_authors = set()
    if bib_author_str:
        for part in bib_author_str.replace(' and ', ',').split(','):
            part = part.strip()
            if part:
                words = part.split()
                if words:
                    bib_authors.add(words[-1].lower())
    
    api_authors = set()
    for a in api_authors_list:
        if a:
            api_authors.add(a.lower())
    
    if bib_authors and api_authors:
        overlap = bib_authors & api_authors
        return len(overlap) > 0, len(overlap)
    return False, 0


def compute_composite_score(citation, api_result):
    """
    Compute a composite verification score (0-100) comparing BibTeX citation
    against an API result.
    - Title match: 50% weight
    - Author overlap: 30% weight  
    - Year match: 20% weight
    """
    score = 0.0
    
    # Title similarity (0-50 points)
    title_sim = calculate_title_similarity(
        citation.get('title', ''),
        api_result.get('title', '')
    )
    score += (title_sim / 100) * 50
    
    # Author overlap (0-30 points)
    has_overlap, _ = check_author_overlap(
        citation.get('author', ''),
        api_result.get('authors', [])
    )
    if has_overlap:
        score += 30
    
    # Year match (0-20 points)
    bib_year = citation.get('year', '').strip()
    api_year = str(api_result.get('year', '')).strip()
    if bib_year and api_year and bib_year != 'None' and api_year != 'None':
        try:
            diff = abs(int(bib_year) - int(api_year))
            if diff == 0:
                score += 20
            elif diff == 1:
                score += 10
        except ValueError:
            pass
    
    return score


def classify_citation(verification_result):
    """
    Classify a citation as 'Real' or 'Fake' based on verification results.
    
    Logic:
    1. If DOI exists and resolves via CrossRef: Real
    2. If no DOI or DOI fails: check API search results
       a. If title similarity >= 95 (near-exact match): Real
       b. If title similarity >= 85 AND author overlap exists: Real
       c. If best composite score >= 70: Real
       d. Otherwise: Fake
    
    The key insight: a high but not exact title match (85-95) without any
    author overlap likely means we found a SIMILAR but DIFFERENT paper,
    which is a hallmark of hallucinated citations.
    """
    if verification_result.get('doi_exists'):
        return 'Real'
    
    citation_data = {
        'title': verification_result.get('title', ''),
        'author': verification_result.get('author', ''),
        'year': verification_result.get('year', ''),
    }
    
    best_composite = 0
    best_title_sim = 0
    best_title_with_author = 0  # best title sim where authors also match
    
    all_results = (
        verification_result.get('crossref_results', []) +
        verification_result.get('semantic_scholar_results', []) +
        verification_result.get('dblp_results', [])
    )
    
    for result in all_results:
        composite = compute_composite_score(citation_data, result)
        title_sim = calculate_title_similarity(
            citation_data['title'], result.get('title', '')
        )
        has_author_overlap, _ = check_author_overlap(
            citation_data.get('author', ''),
            result.get('authors', [])
        )
        
        best_composite = max(best_composite, composite)
        best_title_sim = max(best_title_sim, title_sim)
        
        if has_author_overlap:
            best_title_with_author = max(best_title_with_author, title_sim)
    
    # Near-exact title match (>=95) is strong evidence regardless of authors
    if best_title_sim >= 95:
        return 'Real'
    
    # High title match (>=85) but ONLY if authors also overlap
    if best_title_with_author >= 85:
        return 'Real'
    
    # Composite score threshold (includes author+year weighting)
    if best_composite >= 70:
        return 'Real'
    
    return 'Fake'


def export_fake_citations_json(fake_titles, output_file):
    """
    Export fake citation titles to a JSON file.
    Titles are cleaned and sorted alphabetically.
    """
    cleaned = []
    for title in fake_titles:
        t = re.sub(r'[{}]', '', title)
        t = re.sub(r'\\[a-zA-Z]+\s*', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        if t:
            cleaned.append(t)
    
    cleaned.sort()
    
    result = {"fake_citations": cleaned}
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result
