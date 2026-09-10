# Skill Creation Plan

**Task**: Scrape two Paul Graham essays from paulgraham.com and convert them to a single audiobook MP3 using TTS APIs (OpenAI/ElevenLabs) with local fallback

**Rationale**: The task has two distinct functional domains: (1) web scraping and text extraction/cleaning, and (2) TTS synthesis with API fallback and audio concatenation. Separating these concerns allows each skill to be independently reusable and testable, while keeping the decomposition minimal.

**Number of skills**: 2

---

## Skill 1: evo-web-essay-scraper

**Description**: Scrapes and extracts clean text from Paul Graham's essays on paulgraham.com. Handles the site's legacy table-based HTML, character encoding issues, and navigational boilerplate removal. Also provides text chunking utilities for downstream TTS consumption.

**Responsibility**: Fetching essay HTML, parsing DOM to extract essay body text, cleaning text artifacts, and chunking text into API-safe segments (respecting character limits)

**Key functions**: `scrape_pg_essay`, `clean_text`, `chunk_text`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-web-essay-scraper/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-tts-audiobook-synth

**Description**: Converts text chunks into speech audio using a cascading fallback strategy: tries OpenAI TTS first, then ElevenLabs, then local TTS (edge-tts/gTTS). Handles API authentication, rate limiting, binary audio capture, and concatenation of chunk audio segments into a single MP3 file.

**Responsibility**: TTS API integration (OpenAI, ElevenLabs, edge-tts, gTTS), retry/backoff logic, MP3 chunk generation, and audio concatenation into final output file

**Key functions**: `synthesize_with_openai`, `synthesize_with_elevenlabs`, `synthesize_with_local_tts`, `synthesize_text_to_audio`, `concatenate_audio_chunks`

**Depends on**: evo-web-essay-scraper


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-tts-audiobook-synth/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
