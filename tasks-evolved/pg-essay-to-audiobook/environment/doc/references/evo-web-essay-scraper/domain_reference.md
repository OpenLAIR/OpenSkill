# Domain Reference for evo-web-essay-scraper

**Responsibility**: Fetching essay HTML, parsing DOM to extract essay body text, cleaning text artifacts, and chunking text into API-safe segments (respecting character limits)

**Key functions to implement**: scrape_pg_essay, clean_text, chunk_text

---

## 1. Scraping Paul Graham Essays


The initial phase of the pipeline involves extracting clean, highly accurate text from the target website. Paul Graham's website (paulgraham.com) utilizes a minimalist, historically consistent HTML structure, which presents both advantages and unique challenges for web scraping.

## 5. Text Chunking Strategy


To abide by the 4096-character limit of OpenAI [cite: 3, 4] or the limits of ElevenLabs (5,000 to 40,000 depending on the model) [cite: 14, 15, 16], the essay must be split.