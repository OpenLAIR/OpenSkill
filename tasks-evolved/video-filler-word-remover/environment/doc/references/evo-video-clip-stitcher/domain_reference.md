# Domain Reference for evo-video-clip-stitcher

**Responsibility**: Frame-accurate video clip extraction with re-encoding (libx264/aac), timestamp padding for acoustic continuity, temporary clip file management, concat demuxer list generation, and final video concatenation with stream copy.

**Key functions to implement**: extract_clip, concatenate_clips, build_filler_compilation

---

## 4. Video Clip Extraction and Concatenation with FFmpeg


Once the temporal coordinates `(start, end)` of the filler words are identified, the next phase is to manipulate the multimedia file. Extracting hundreds of short (0.5s - 1.5s) clips and stitching them together introduces significant complexities involving video keyframes and presentation timestamps (PTS).

### 4.1 Frame-Accurate Clip Extraction

Standard `ffmpeg` trimming relies on the `-ss` (seek) and `-to` (or `-t` duration) parameters [cite: 30, 31, 32]. The placement of these parameters drastically alters how `ffmpeg` operates:

1.  **Fast Seek (Inaccurate)**: `ffmpeg -ss {start} -i input.mp4`
    Seeking *before* the input parses only to the nearest preceding **I-frame (keyframe)** [cite: 31, 33]. For a filler word clip that lasts 0.5 seconds, the nearest keyframe might be 3 seconds away. Using stream copy (`-c copy`) with fast seek will result in clips that start entirely at the wrong timestamp, containing video that precedes the filler word [cite: 32, 34].
2.  **Output Seek (Accurate but Slow)**: `ffmpeg -i input.mp4 -ss {start}`
    Seeking *after* the input decodes the video frame-by-frame from the beginning to find the exact sub-second timestamp [cite: 31]. 

**The Re-encoding Imperative:**
For sub-second precision, **stream copying (`-c copy`) must be abandoned**. Attempting to stream copy a 0.5-second clip between two P-frames will result in broken PTS, frozen video, and audio desynchronization [cite: 34]. The video *must* be re-encoded (`-c:v libx264 -c:a aac`) to guarantee that the cut starts and ends exactly on the provided timestamps with a newly generated keyframe at the start of the output clip [cite: 34].

To combine processing speed with frame accuracy, the optimal approach is a **combined seek with re-encoding**: use a fast seek to get close to the timestamp, then re-encode the precise duration [cite: 34].

```python

### 4.2 Concatenation Logic

Combining the extracted clips back into a single `output.mp4` can be done using the `concat demuxer` or the `concat filter` [cite: 37, 38, 39]. 

*   **Concat Filter (`-filter_complex`)**: Forces complete re-encoding of all streams into one. Highly reliable but extremely slow and computationally heavy [cite: 37, 39].
*   **Concat Demuxer**: Reads a text list of files and merges them sequentially at the stream level without re-encoding. Because we already normalized and re-encoded our individual clips into the exact same codec (`libx264`/`aac`), the concat demuxer is safe, incredibly fast, and the absolute optimal choice [cite: 37, 40].

**Concat Demuxer List Format:**
The list must be a plain text file (`list.txt`) encoded in UTF-8, containing absolute or relative paths preceded by the word `file` [cite: 37, 40].
```text
file 'temp_clip_0.mp4'
file 'temp_clip_1.mp4'
```

**Executing the Concat Demuxer via Python:**
```python
def concatenate_clips(clip_paths: list, output_path: str):
    list_file_path = "concat_list.txt"
    
    # Generate the safe list text file
    with open(list_file_path, "w", encoding="utf-8") as f:
        for clip in clip_paths:
            # Ensure paths are wrapped in single quotes for ffmpeg parser safety
            f.write(f"file '{os.path.abspath(clip)}'\n")
            
    command = [
        "ffmpeg", "-y",
        "-f", "concat",          # Use concat demuxer
        "-safe", "0",            # Allow absolute paths in the list file
        "-i", list_file_path,    # Pass the text file as input
        "-c", "copy",            # Stream copy (NO re-encoding needed here)
        output_path
    ]
    
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Clean up the list file
    os.remove(list_file_path)
```
*Note: The `-safe 0` parameter is mandatory if your `list.txt` contains absolute paths or paths outside the immediate working directory [cite: 37, 40, 41].*

---

### 6.2 Timestamp Accuracy and Temporal Drift

Whisper's temporal resolution is natively constrained to 20-millisecond windows due to its convolutional sub-sampling layer (feature extractor) [cite: 3, 15]. 
*   **Word Boundaries**: The word boundaries provided by the DTW cross-attention algorithms are estimates. They are remarkably accurate for clear speech but can become "fuzzy" during rapid speech or overlapping dialogue [cite: 5, 23].
*   **Padding**: Because boundaries are not mathematically flawless, clipping video identically to the `[start, end]` tuples often cuts off the initial transient or trailing tail of the filler word utterance. Adding a static padding of **0.15s to 0.25s** to the start and end (as demonstrated in Section 4.1) is vital to ensure acoustic continuity [cite: 28].
*   **Drift**: Over exceedingly long files (e.g., >2 hours), internal timestamp drift can occur. The built-in Silero VAD segmentation in `faster-whisper` effectively acts as an algorithmic reset, breaking the audio into discrete chunks and preventing catastrophic temporal drift across long transcripts [cite: 25, 26].