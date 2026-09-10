"""
evo-citation-verifier utility functions.
Queries external academic APIs to verify whether citations exist.
"""
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


POLITE_EMAIL = "citation-verifier@example.com"
DEFAULT_HEADERS = {
    "User-Agent": f"CitationVerifier/1.0 (mailto:{POLITE_EMAIL})"
}


def get_robust_session():
    """Create a requests session with retry logic and exponential backoff."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session


def rate_limited_query(session, url, params, headers=None, delay=1.5):
    """Execute a rate-limited GET request with delay."""
    try:
        response = session.get(url, params=params, headers=headers, timeout=15)
        time.sleep(delay)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def verify_doi_exists(doi, session=None):
    """
    Check if a DOI resolves via CrossRef API.
    Returns (exists: bool, metadata: dict or None)
    """
    if not doi:
        return False, None
    
    doi = doi.strip()
    if session is None:
        session = get_robust_session()
    
    url = f"https://api.crossref.org/works/{doi}"
    try:
        response = session.get(url, timeout=15)
        time.sleep(1.0)
        if response.status_code == 200:
            data = response.json()
            msg = data.get('message', {})
            return True, {
                'title': msg.get('title', [''])[0] if msg.get('title') else '',
                'authors': [a.get('family', '') for a in msg.get('author', [])],
                'year': str(msg.get('published-print', {}).get('date-parts', [[None]])[0][0] or 
                           msg.get('published-online', {}).get('date-parts', [[None]])[0][0] or ''),
            }
        return False, None
    except Exception as e:
        print(f"DOI verification error for {doi}: {e}")
        return False, None


def query_crossref(title, session=None, author_hint=""):
    """
    Search CrossRef by title (and optionally author). Returns top results.
    """
    if not title:
        return []
    
    if session is None:
        session = get_robust_session()
    
    query_str = title
    if author_hint:
        query_str = f"{title} {author_hint}"
    
    params = {
        "query.bibliographic": query_str,
        "rows": 5,
        "mailto": POLITE_EMAIL
    }
    
    data = rate_limited_query(session, "https://api.crossref.org/works", params)
    if data:
        items = data.get('message', {}).get('items', [])
        results = []
        for item in items:
            results.append({
                'title': item.get('title', [''])[0] if item.get('title') else '',
                'authors': [a.get('family', '') for a in item.get('author', [])],
                'year': str(item.get('published-print', {}).get('date-parts', [[None]])[0][0] or 
                           item.get('published-online', {}).get('date-parts', [[None]])[0][0] or ''),
                'score': item.get('score', 0),
            })
        return results
    return []


def query_semantic_scholar(title, session=None):
    """
    Search Semantic Scholar by title. Returns top results.
    """
    if not title:
        return []
    
    if session is None:
        session = get_robust_session()
    
    params = {
        "query": title,
        "limit": 3,
        "fields": "title,authors,year,externalIds,venue"
    }
    
    data = rate_limited_query(session, "https://api.semanticscholar.org/graph/v1/paper/search", params, delay=3.0)
    if data:
        results = []
        for item in data.get('data', []):
            results.append({
                'title': item.get('title', ''),
                'authors': [a.get('name', '').split()[-1] for a in item.get('authors', [])],
                'year': str(item.get('year', '')),
                'venue': item.get('venue', ''),
            })
        return results
    return []


def query_dblp(title, session=None):
    """
    Search DBLP by title. Returns top results.
    """
    if not title:
        return []
    
    if session is None:
        session = get_robust_session()
    
    params = {
        "q": title,
        "format": "json",
        "h": 3
    }
    
    data = rate_limited_query(session, "https://dblp.org/search/publ/api", params)
    if data:
        hits = data.get('result', {}).get('hits', {}).get('hit', [])
        results = []
        for hit in hits:
            info = hit.get('info', {})
            authors_data = info.get('authors', {}).get('author', [])
            if isinstance(authors_data, dict):
                authors_data = [authors_data]
            results.append({
                'title': info.get('title', ''),
                'authors': [a.get('text', '').split()[-1] if isinstance(a, dict) else str(a).split()[-1] for a in authors_data],
                'year': str(info.get('year', '')),
                'venue': info.get('venue', ''),
            })
        return results
    return []


def _extract_first_author_lastname(author_str):
    """Extract the first author's last name from a BibTeX author string."""
    if not author_str:
        return ""
    # Split by 'and' to get first author
    first = author_str.split(' and ')[0].strip()
    if ',' in first:
        # "LastName, FirstName" format
        return first.split(',')[0].strip()
    else:
        # "FirstName LastName" format
        parts = first.split()
        return parts[-1].strip() if parts else ""


def verify_citation(citation, session=None):
    """
    Verify a single citation against multiple APIs.
    Returns dict with verification results.
    
    Strategy:
    1. If DOI present, verify via CrossRef DOI lookup
    2. If DOI fails/absent, search CrossRef by title
    3. If title-only search is weak, retry with author hint
    """
    if session is None:
        session = get_robust_session()
    
    result = {
        'id': citation.get('id', ''),
        'title': citation.get('title', ''),
        'doi_exists': False,
        'doi_metadata': None,
        'crossref_results': [],
        'semantic_scholar_results': [],
        'dblp_results': [],
    }
    
    # Step 1: Check DOI if present
    doi = citation.get('doi', '')
    if doi:
        exists, metadata = verify_doi_exists(doi, session)
        result['doi_exists'] = exists
        result['doi_metadata'] = metadata
    
    # Step 2: If DOI failed or absent, search by title
    if not result['doi_exists']:
        title = citation.get('title', '')
        
        # First try title-only search
        result['crossref_results'] = query_crossref(title, session)
        
        # Step 3: Also try with author hint for better results
        author_str = citation.get('author', '')
        first_author = _extract_first_author_lastname(author_str)
        if first_author:
            author_results = query_crossref(title, session, author_hint=first_author)
            # Merge results (avoid duplicates by title)
            existing_titles = {r['title'].lower() for r in result['crossref_results']}
            for ar in author_results:
                if ar['title'].lower() not in existing_titles:
                    result['crossref_results'].append(ar)
                    existing_titles.add(ar['title'].lower())
    
    return result
