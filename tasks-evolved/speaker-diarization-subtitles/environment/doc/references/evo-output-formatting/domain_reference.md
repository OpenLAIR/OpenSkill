# Domain Reference for evo-output-formatting

**Responsibility**: Formatting and writing RTTM diarization files, ASS subtitle files with centisecond time conversion and speaker labels, and JSON report generation.

**Key functions to implement**: export_rttm, format_ass_time, export_ass_subtitles, generate_report_json

---

## 7. RTTM File Format Specification and Pyannote.core


Rich Transcription Time Marked (RTTM) is the standard format for representing speaker diarization timelines [cite: 24].

### 7.1 Exact Column Format

An RTTM file is a space-delimited text file. For speaker diarization, each line follows this rigid structure:
`SPEAKER <file_id> 1 <start_time> <duration> <NA> <NA> <speaker_label> <NA> <NA>`

*   `SPEAKER`: Literal string indicating a speaker segment.
*   `<file_id>`: The URI or filename (without extension).
*   `1`: Channel ID (usually 1).
*   `<start_time>`: Start time in seconds (float).
*   `<duration>`: Duration in seconds (float).
*   `<NA>`: Orthography (not used in diarization).
*   `<NA>`: Subtype (not used).
*   `<speaker_label>`: The assigned speaker ID (e.g., `spk00`).
*   `<NA>`: Confidence score (not used).
*   `<NA>`: Speaker Lookahead (not used).

## 8. ASS (Advanced SubStation Alpha) Subtitle Format


While RTTM is for machine evaluation, ASS is the premier format for visual subtitle rendering, enabling styling and absolute positioning [cite: 7, 26].

### 8.1 Complete Header and Preamble

A valid ASS file requires specific sections: `[Script Info]`, `[V4+ Styles]`, and `[Events]` [cite: 8, 26].

```text
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
```

### 8.2 Dialogue Lines and Centiseconds Conversion

The format for a subtitle line is:
`Dialogue: 0,H:MM:SS.cc,H:MM:SS.cc,Default,,0,0,0,,Text` [cite: 7, 8, 27].

The time format requires conversion from floating seconds to `H:MM:SS.cc` (hours, minutes, seconds, and centiseconds) [cite: 7, 8, 26].

```python
def format_ass_time(seconds: float) -> str:
    """Converts float seconds to H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int(round((seconds - int(seconds)) * 100))
    
    # Handle rollover if centisecs rounds to 100
    if centisecs == 100:
        centisecs = 0
        secs += 1
        if secs == 60:
            secs = 0
            minutes += 1
            
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
```

### 8.3 Injecting Speaker Labels

To include the speaker label in the subtitle, simply prefix the text block.
```python
start_ass = format_ass_time(word_start)
end_ass = format_ass_time(word_end)
speaker = "spk00"
text = "Hello there."

ass_line = f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{\\b1}{speaker}:{\\b0} {text}\n"
```
*(The `{\b1}` and `{\b0}` ASS tags toggle bold formatting for the speaker name).*

---

### 9.4 Pyannote.core Immutability Gotchas

Objects like `pyannote.core.Segment` and `pyannote.core.Timeline` have strict immutability rules. A `Segment` cannot have its `start` or `end` attributes altered post-instantiation [cite: 9]. You must instantiate a new `Segment`. While the `Annotation` object behaves like a dictionary, overlapping segments assigned to the exact same track will override each other, so ensure uniqueness or use multi-track allocation if mapping overlapping speech.

---