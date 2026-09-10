import requests
from bs4 import BeautifulSoup
import re


def scrape_pg_essay(url: str) -> str:
    """Fetches and extracts clean text from a Paul Graham essay URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the main content table (width ~435 or ~410)
    content_table = soup.find('table', width=re.compile(r'4[0-3]\d'))
    
    if content_table:
        # Use get_text directly on the table to avoid duplicates from nested tags
        raw_text = content_table.get_text(separator='\n', strip=True)
    else:
        # Fallback: strip body of scripts and styles
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        raw_text = soup.body.get_text(separator='\n', strip=True) if soup.body else soup.get_text(separator='\n', strip=True)
    
    cleaned = clean_text(raw_text)
    return cleaned


def clean_text(text: str) -> str:
    """Cleans text artifacts, encoding issues, and nav boilerplate."""
    # Remove common PG navigation boilerplate
    text = re.sub(r'Want to start a startup\?.*?Y Combinator\s*\.?', '', text, flags=re.DOTALL)
    
    # Fix unicode artifacts
    text = text.replace('\xa0', ' ')
    
    # Remove footnote reference numbers like [1], [2] etc in the text
    # But keep inline references - just remove the footnote section at the end
    # Find where footnotes start (pattern: line with just a number or [number])
    lines = text.split('\n')
    
    # Find the end of main content - look for the "Thanks to" or acknowledgment section end
    # then remove everything after the footnote markers
    clean_lines = []
    footnote_section = False
    seen_thanks = False
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines in sequence
        if not stripped:
            if clean_lines and clean_lines[-1] == '':
                continue
            clean_lines.append('')
            continue
        
        # Detect thanks/acknowledgment section
        if stripped.startswith('Thanks to') or stripped.startswith('Thank you'):
            seen_thanks = True
            clean_lines.append(stripped)
            continue
        
        # After thanks, if we see just numbers or [N] patterns, we're in footnotes
        if seen_thanks and re.match(r'^\[?\s*\d+\s*\]?$', stripped):
            footnote_section = True
            continue
        
        if footnote_section:
            # Skip footnote content (just numbers)
            if re.match(r'^\d+$', stripped):
                continue
            # If we see substantial text again, might be footnote text - skip
            continue
        
        clean_lines.append(stripped)
    
    text = '\n'.join(clean_lines)
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()


def chunk_text(text: str, max_chars: int = 4000) -> list:
    """Splits text into chunks respecting sentence boundaries."""
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_chars:
            current_chunk += sentence + " "
        else:
            if len(sentence) > max_chars:
                words = sentence.split(" ")
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chars:
                        current_chunk += word + " "
                    else:
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = word + " "
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks
