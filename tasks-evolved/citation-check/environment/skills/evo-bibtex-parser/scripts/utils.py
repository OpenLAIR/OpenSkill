"""
evo-bibtex-parser utility functions.
Parses BibTeX files using bibtexparser 1.4.2 and cleans LaTeX/BibTeX artifacts.
"""
import re
import bibtexparser
from bibtexparser.bparser import BibTexParser


def parse_bibtex_file(file_path):
    """
    Parses a BibTeX file using bibtexparser 1.4.2 and returns a list of entry dicts.
    Uses homogenize_fields=True to standardize field names to lowercase.
    """
    parser = BibTexParser(common_strings=True)
    parser.homogenize_fields = True
    parser.ignore_nonstandard_types = False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as bibtex_file:
            bib_database = bibtexparser.load(bibtex_file, parser=parser)
            return bib_database.entries
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return []


def clean_bibtex_artifacts(text):
    """
    Removes BibTeX/LaTeX formatting artifacts from a string:
    - Curly braces {}
    - Common LaTeX escape sequences
    - Multiple spaces and newlines
    """
    if not text:
        return ""
    
    # Remove curly braces used for capitalization protection
    text = re.sub(r'[{}]', '', text)
    
    # Handle common LaTeX character escapes
    latex_replacements = {
        r"\\'a": "a", r"\\'e": "e", r"\\'i": "i", r"\\'o": "o", r"\\'u": "u",
        r'\\"a': "a", r'\\"e': "e", r'\\"i': "i", r'\\"o': "o", r'\\"u': "u",
        r"\\`a": "a", r"\\`e": "e", r"\\`i": "i", r"\\`o": "o", r"\\`u": "u",
        r"\\~n": "n", r"\\^o": "o", r"\\c{c}": "c",
        r"\\&": "&", r"\\%": "%",
    }
    for latex, replacement in latex_replacements.items():
        text = text.replace(latex, replacement)
    
    # Remove remaining backslash commands like \v{Z}, \'{\i}
    text = re.sub(r'\\[a-zA-Z]+\s*', '', text)
    
    # Clean up multiple spaces and newline characters
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_citation_metadata(entries):
    """
    Extracts and cleans metadata from parsed BibTeX entries.
    Returns a list of dicts with cleaned fields: id, type, title, author, year, doi, venue.
    """
    processed = []
    for entry in entries:
        entry_id = entry.get('ID', 'unknown_id')
        entry_type = entry.get('ENTRYTYPE', 'misc')
        
        title = clean_bibtex_artifacts(entry.get('title', ''))
        author = clean_bibtex_artifacts(entry.get('author', ''))
        year = entry.get('year', '').strip()
        doi = clean_bibtex_artifacts(entry.get('doi', ''))
        
        journal = entry.get('journal', '')
        booktitle = entry.get('booktitle', '')
        venue = clean_bibtex_artifacts(journal if journal else booktitle)
        
        processed.append({
            'id': entry_id,
            'type': entry_type,
            'title': title,
            'author': author,
            'year': year,
            'doi': doi,
            'venue': venue,
        })
    return processed
