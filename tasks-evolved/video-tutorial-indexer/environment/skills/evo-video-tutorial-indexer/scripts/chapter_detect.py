"""
Chapter detection module using sliding window fuzzy string matching.

Domain insights applied:
- Speakers rarely say chapter titles verbatim, so fuzzy matching is essential
- Sliding window of N words (title word count + margin) catches multi-word phrases
- token_set_ratio handles word reordering and partial matches well
- Multiple matching strategies (fuzzy, keyword clusters, verbal cues) improve recall
- Monotonic enforcement with minimum gap prevents timestamp collisions
- Short chapters like "Save", "Break", "Great job!" need special keyword handling
"""

import re
from typing import List, Dict, Optional, Tuple


def _normalize_text(text):
    """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    # Keep apostrophes in contractions but remove other punctuation
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get_fuzzy_score(target, candidate):
    """
    Compute fuzzy match score between target and candidate strings.
    Uses token_set_ratio which handles substrings and word reordering well.
    Falls back to simple substring matching if thefuzz is not available.
    """
    try:
        from thefuzz import fuzz
        # token_set_ratio is best for cases where candidate may contain extra words
        score1 = fuzz.token_set_ratio(target, candidate)
        # partial_ratio catches substring matches
        score2 = fuzz.partial_ratio(target, candidate)
        # Also try token_sort_ratio for reordered words
        score3 = fuzz.token_sort_ratio(target, candidate)
        return max(score1, score2, score3)
    except ImportError:
        # Fallback: simple substring containment check
        target_lower = target.lower()
        candidate_lower = candidate.lower()
        if target_lower in candidate_lower:
            return 95
        # Check word overlap
        target_words = set(target_lower.split())
        candidate_words = set(candidate_lower.split())
        if not target_words:
            return 0
        overlap = len(target_words & candidate_words) / len(target_words)
        return int(overlap * 100)


def _build_keyword_map():
    """
    Build keyword clusters for chapter titles that may not be spoken verbatim.
    These are domain-specific patterns for Blender tutorial chapters.
    """
    return {
        "what we'll do": ["what we'll do", "what we will do", "what we're going to do", "what we are going to do", "going to create", "going to make", "going to build"],
        "how we'll get there": ["how we'll get there", "how we will get there", "how we're going to get there", "steps", "process", "workflow"],
        "getting a floor plan": ["floor plan", "get a floor plan", "find a floor plan", "getting a floor plan", "floor plan image"],
        "getting started": ["getting started", "get started", "let's get started", "let's start", "open blender", "start blender"],
        "basic navigation": ["basic navigation", "navigation", "navigate", "middle mouse", "scroll", "orbit", "pan", "zoom"],
        "import your plan into blender": ["import", "bring in", "load", "open the", "background image", "import your plan"],
        "basic transform operations": ["transform", "grab", "rotate", "scale", "move", "g key", "r key", "s key", "basic transform"],
        "setting up the plan and units": ["units", "metric", "setting up", "set up the plan", "plan and units", "measurement"],
        "it all starts with a plane": ["starts with a plane", "add a plane", "mesh plane", "start with a plane", "all starts with a plane"],
        "scaling the plane to real dimensions": ["scaling the plane", "real dimensions", "real size", "actual size", "scale the plane", "real dimension"],
        "getting the plan in place": ["plan in place", "position the plan", "getting the plan", "align the plan"],
        "tracing the outline": ["tracing the outline", "trace the outline", "outer walls", "outline", "tracing outline", "trace outline"],
        "tracing inner walls": ["tracing inner walls", "trace inner walls", "inner walls", "interior walls", "inside walls"],
        "break": ["break", "take a break", "pause", "breather", "quick break"],
        "continue tracing inner walls": ["continue tracing", "continue inner walls", "keep tracing", "resume", "back to tracing", "continue tracing inner"],
        "remove doubled vertices": ["doubled vertices", "double vertices", "remove doubles", "merge by distance", "merge vertices", "duplicate vertices"],
        "save": ["save", "ctrl s", "control s", "save your file", "save the file", "let's save"],
        "make the floor": ["make the floor", "create the floor", "floor", "make floor"],
        "remove unnecessary geometry": ["remove unnecessary", "unnecessary geometry", "delete", "clean up", "remove geometry"],
        "make the floor's faces": ["floor's faces", "floor faces", "make faces", "fill faces", "create faces", "face", "fill"],
        "make the background": ["background", "make the background", "create background", "background plane"],
        "extruding the walls in z": ["extrude", "extruding", "walls in z", "z axis", "extrude walls", "push up", "pull up"],
        "reviewing face orientation": ["face orientation", "normals", "reviewing face", "face direction", "blue and red"],
        "adding thickness to walls with modifiers": ["thickness", "solidify", "modifier", "modifiers", "adding thickness", "wall thickness"],
        "fixing face orientation errors": ["fixing face", "fix face", "fix normals", "recalculate", "flip normals", "fixing face orientation"],
        "note on face orientation": ["note on face", "note about face", "note on normals", "keep in mind", "important note"],
        "save as": ["save as", "save a copy", "save as a", "different name", "new name"],
        "if you need thick and thin walls": ["thick and thin", "different thickness", "thick and thin walls", "varying thickness", "different wall"],
        "great job": ["great job", "good job", "well done", "congratulations", "that's it", "you did it", "awesome"],
    }


def find_chapter_timestamp(
    target_title: str,
    all_words: List[Dict],
    keyword_map: Dict,
    search_start: float = 0.0,
    search_end: float = float('inf'),
    threshold: int = 70
) -> Tuple[Optional[float], int]:
    """
    Find the timestamp where a chapter title is first spoken using multiple strategies.
    
    Strategy 1: Sliding window fuzzy match against the title
    Strategy 2: Keyword cluster matching for domain-specific phrases
    Strategy 3: Individual keyword spotting for short titles (e.g., "Save", "Break")
    
    Returns (timestamp_seconds, confidence_score) or (None, 0).
    """
    if not all_words:
        return None, 0

    target_normalized = _normalize_text(target_title)
    target_key = target_normalized.rstrip("'s").rstrip("s")  # rough stem
    title_word_count = len(target_normalized.split())

    best_time = None
    best_score = 0

    # Filter words to search range
    search_words = [
        w for w in all_words
        if w.get("start", 0) >= search_start and w.get("start", 0) <= search_end
    ]

    if not search_words:
        return None, 0

    # Strategy 1: Sliding window fuzzy matching
    # Window size = title word count + margin, but at least 2 and at most 10
    window_size = max(2, min(title_word_count + 3, 10))

    for i in range(len(search_words)):
        end_idx = min(i + window_size, len(search_words))
        window = search_words[i:end_idx]
        window_text = _normalize_text(" ".join(w.get("word", "").strip() for w in window))

        if not window_text:
            continue

        score = _get_fuzzy_score(target_normalized, window_text)

        if score > best_score and score >= threshold:
            best_score = score
            best_time = window[0].get("start", 0)

            # Early exit on very high confidence
            if score >= 95:
                break

    # Strategy 2: Keyword cluster matching (if fuzzy didn't find a strong match)
    if best_score < 85:
        keywords = keyword_map.get(target_normalized, [])
        for keyword_phrase in keywords:
            kw_words = keyword_phrase.split()
            kw_window_size = max(len(kw_words) + 2, 3)

            for i in range(len(search_words)):
                end_idx = min(i + kw_window_size, len(search_words))
                window = search_words[i:end_idx]
                window_text = _normalize_text(" ".join(w.get("word", "").strip() for w in window))

                if not window_text:
                    continue

                score = _get_fuzzy_score(keyword_phrase, window_text)

                # Keyword matches get a slight penalty since they're indirect
                adjusted_score = int(score * 0.9)

                if adjusted_score > best_score and adjusted_score >= threshold:
                    best_score = adjusted_score
                    best_time = window[0].get("start", 0)

    # Strategy 3: Single keyword spotting for very short titles
    if best_score < threshold and title_word_count <= 2:
        # For titles like "Save", "Break", "Great job!" look for exact word matches
        core_words = [w for w in target_normalized.split() if len(w) > 2]
        for i, word_entry in enumerate(search_words):
            word_text = _normalize_text(word_entry.get("word", ""))
            for core in core_words:
                if core in word_text or word_text in core:
                    candidate_score = 72
                    if candidate_score > best_score:
                        best_score = candidate_score
                        best_time = word_entry.get("start", 0)
                    break
            if best_score >= 72:
                break

    return best_time, best_score


def detect_chapters(
    chapter_titles: List[str],
    transcript_result: Dict,
    duration: int = 1382,
    threshold: int = 65
) -> List[Dict]:
    """
    Detect all chapter timestamps from a Whisper transcript.
    
    Uses a forward-scanning approach: each chapter's search window starts
    slightly before the previous chapter's detected timestamp to allow for
    minor corrections, but generally moves forward through the video.
    
    Args:
        chapter_titles: Ordered list of expected chapter titles
        transcript_result: Whisper transcribe() result dict
        duration: Video duration in seconds
        threshold: Minimum fuzzy match score to accept
    
    Returns:
        List of {"time": int, "title": str} dicts
    """
    # Import here to allow the module to load even without whisper
    try:
        from transcribe import get_all_words
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from transcribe import get_all_words

    all_words = get_all_words(transcript_result)
    keyword_map = _build_keyword_map()

    if not all_words:
        print("WARNING: No words found in transcript. Using evenly spaced fallback.")
        return _evenly_spaced_fallback(chapter_titles, duration)

    print(f"Searching for {len(chapter_titles)} chapters in {len(all_words)} words...")

    chapters = []
    last_found_time = 0.0

    for idx, title in enumerate(chapter_titles):
        # First chapter is always at time 0
        if idx == 0:
            chapters.append({"time": 0, "title": title})
            continue

        # Search window: start from slightly before last found time
        # This allows some overlap for correction but generally moves forward
        search_start = max(0, last_found_time - 5.0)

        # For the last few chapters, don't restrict the end too much
        # Estimate a reasonable search end based on position in chapter list
        estimated_end = min(
            duration,
            (idx + 3) * (duration / len(chapter_titles))
        )
        search_end = max(estimated_end, last_found_time + 120)
        search_end = min(search_end, duration)

        timestamp, confidence = find_chapter_timestamp(
            title, all_words, keyword_map,
            search_start=search_start,
            search_end=search_end,
            threshold=threshold
        )

        if timestamp is not None:
            # Ensure we don't go backwards
            if timestamp <= last_found_time:
                timestamp = last_found_time + 1.0
            chapters.append({"time": int(round(timestamp)), "title": title})
            last_found_time = timestamp
            print(f"  [{idx + 1:2d}/{len(chapter_titles)}] '{title}' -> {int(round(timestamp))}s (confidence: {confidence})")
        else:
            # Fallback: interpolate between last found and estimated position
            fallback_time = last_found_time + max(5, (duration / len(chapter_titles)) * 0.5)
            fallback_time = min(fallback_time, duration - (len(chapter_titles) - idx))
            chapters.append({"time": int(round(fallback_time)), "title": title})
            last_found_time = fallback_time
            print(f"  [{idx + 1:2d}/{len(chapter_titles)}] '{title}' -> {int(round(fallback_time))}s (INTERPOLATED)")

    return chapters


def enforce_monotonic(chapters: List[Dict], duration: int = 1382, min_gap: int = 1) -> List[Dict]:
    """
    Enforce strictly monotonically increasing timestamps with minimum gap.
    
    Also ensures:
    - First chapter at time 0
    - All timestamps within [0, duration]
    - At least min_gap seconds between consecutive chapters
    
    This is a post-processing safety net. The detection should already produce
    mostly-monotonic results, but edge cases (interpolation, fuzzy match errors)
    can create violations.
    """
    if not chapters:
        return chapters

    result = []

    for i, ch in enumerate(chapters):
        t = ch["time"]

        if i == 0:
            t = 0
        else:
            # Must be at least min_gap after previous
            prev_time = result[-1]["time"]
            if t <= prev_time:
                t = prev_time + min_gap

        # Clamp to valid range
        t = max(0, min(t, duration))

        result.append({"time": t, "title": ch["title"]})

    # Final pass: if the last chapters got squeezed against duration,
    # redistribute from the end backwards
    for i in range(len(result) - 1, 0, -1):
        if result[i]["time"] <= result[i - 1]["time"]:
            result[i - 1]["time"] = max(0, result[i]["time"] - min_gap)

    # Ensure first is still 0
    result[0]["time"] = 0

    return result


def _evenly_spaced_fallback(chapter_titles: List[str], duration: int) -> List[Dict]:
    """
    Last-resort fallback: evenly space chapters across the video duration.
    This should rarely be needed but prevents total failure.
    """
    n = len(chapter_titles)
    chapters = []
    for i, title in enumerate(chapter_titles):
        t = int(round(i * duration / n))
        chapters.append({"time": t, "title": title})
    chapters[0]["time"] = 0
    return chapters