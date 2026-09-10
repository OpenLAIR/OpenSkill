# Domain Reference for evo-speech-filler-detection

**Responsibility**: Audio extraction from video via ffmpeg subprocess, speech-to-text transcription using faster-whisper with optimized CPU settings, text normalization (lowercasing, punctuation stripping, whitespace handling), single-word and multi-word filler phrase detection using n-gram sliding window, and JSON annotation output.

**Key functions to implement**: extract_audio_for_whisper, transcribe_with_word_timestamps, normalize_word, detect_filler_words, save_annotations_json

---

## 1. Whisper Model Frameworks and Word-Level Timestamps


The OpenAI Whisper architecture has become the de facto standard for open-source automatic speech recognition (ASR) [cite: 1, 2]. However, the canonical implementation is poorly suited for resource-constrained, CPU-only environments. Selecting the appropriate implementation and understanding its precise API for temporal token alignment is the foundational step in building a filler-word detection module.

### 1.1 Package Ecosystem: `whisper` vs `faster-whisper` vs `openai-whisper`


The Python ecosystem contains multiple implementations of the Whisper model, which can cause significant dependency and namespace confusion:

1.  **`openai-whisper`**: This is the official package provided by OpenAI. The pip install name is `openai-whisper` (though often aliased or confused with a generic `whisper` package). The import path in Python is `import whisper` [cite: 1, 3]. It relies heavily on PyTorch and requires substantial disk space and memory [cite: 2]. It supports word-level timestamps natively in newer versions using Dynamic Time Warping (DTW) across cross-attention weights [cite: 4, 5].
2.  **`faster-whisper`**: A third-party, highly optimized reimplementation of Whisper utilizing the CTranslate2 inference engine [cite: 6, 7]. The pip package name is `faster-whisper`, and the import path is `import faster_whisper` or `from faster_whisper import WhisperModel` [cite: 8, 9]. It natively supports word-level timestamps, avoids the massive PyTorch dependency, and offers up to 4x faster execution on GPUs and significantly faster execution on CPUs using INT8 quantization [cite: 7, 10].
3.  **`whisper`**: A generic namespace often squatted on PyPI, or used locally. One must explicitly install `openai-whisper` to get the official OpenAI library [cite: 3].

For a `python:3.12-slim` Docker container running on a CPU with a strict 1800-second (30-minute) timeout, **`faster-whisper`** is unequivocally the superior choice [cite: 2, 11]. It circumvents the gigabytes of PyTorch dependencies and utilizes Single Instruction, Multiple Data (SIMD) optimizations for CPU processing.

### 1.2 The `faster-whisper` API and Implementation


The `faster-whisper` library operates using a model class that wraps the CTranslate2 backend.

### 1.4 Model Sizes and the Accuracy vs. Speed Tradeoff


Whisper models exist in multiple parameter counts: `tiny` (39M), `base` (74M), `small` (244M), `medium` (769M), and `large` (1.5B) [cite: 4, 15]. 

For filler word detection on a CPU within a 1800-second timeout window, processing speed is paramount. CPU execution scales linearly with parameter count. 
*   **`tiny` / `base`**: Exceptionally fast, but they frequently skip disfluencies ("um", "uh") because they were trained heavily on normalized text and tend to output cleaner, grammatical transcripts rather than verbatim utterances [cite: 16].
*   **`small` / `small.en`**: Represents the **optimal tradeoff** for CPU extraction [cite: 7]. It possesses enough capacity to accurately recognize filler words and acoustic edge cases, but with `int8` quantization, it processes audio fast enough to comfortably stay under the 1800s timeout (typically achieving around 1.5x to 3x real-time speed on a modern multi-core CPU) [cite: 10, 17].
*   **`medium` / `large`**: These models require excessive RAM (up to 3-6GB even with quantization) and process significantly slower than real-time on CPUs, risking timeout failures [cite: 7, 11].

---

## 2. Audio Extraction from Video using FFmpeg


Whisper models are hardcoded to process audio as 16kHz, mono-channel, 16-bit PCM WAV data arrays. If video files (`.mp4`, `.mkv`) are fed directly into standard Whisper wrappers, the wrapper inherently utilizes `ffmpeg` to extract the audio [cite: 18]. However, explicitly managing this extraction via Python provides superior error handling, validation, and control over temp files.

### 2.1 Subprocess vs. FFmpeg-Python

Integrating `ffmpeg` can be achieved via the `subprocess` module or third-party wrappers like `ffmpeg-python`. For building a robust, reusable utility module, **`subprocess` is demonstrably more reliable** [cite: 18, 19]. Using `subprocess` avoids introducing another third-party pip dependency, ensures exact alignment with `ffmpeg`'s native command-line arguments, and minimizes the debugging surface area.

### 2.2 Extraction Command and Parameters

To extract the exact format Whisper expects, the following `ffmpeg` arguments are required [cite: 20, 21]:
*   `-i {input}`: Specify input video file.
*   `-vn`: Disable video stream processing (dramatically speeds up extraction) [cite: 20].
*   `-acodec pcm_s16le`: Set audio codec to 16-bit little-endian PCM [cite: 20, 22].
*   `-ar 16000`: Set the audio sample rate to 16,000 Hz [cite: 20].
*   `-ac 1`: Downmix the audio to a single (mono) channel [cite: 20].
*   `-y`: Force overwrite of the output file without prompting [cite: 18].

**Python Implementation:**
```python
import subprocess
import os

def extract_audio_for_whisper(video_path: str, output_wav_path: str) -> str:
    """
    Extracts 16kHz mono audio from a video file using ffmpeg.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
        
    command = [
        "ffmpeg",
        "-y",                   # Overwrite output
        "-i", video_path,       # Input file
        "-vn",                  # No video
        "-acodec", "pcm_s16le", # 16-bit PCM codec
        "-ar", "16000",         # 16 kHz sample rate
        "-ac", "1",             # Mono channel
        output_wav_path
    ]
    
    try:
        # Capture stderr to view ffmpeg errors if it fails
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return output_wav_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg audio extraction failed: {e.stderr}")
```

---

## 3. Filler Word Detection Logic


Accurately detecting filler words from Whisper's temporal word outputs is a complex task due to the model's tokenization artifacts and the natural disfluencies of conversational speech [cite: 23]. Whisper does not output clean, space-delimited text natively; its tokens contain leading spaces and erratic capitalization.

### 3.1 Normalizing Whisper Transcripts

To match against a predefined list of filler words (e.g., `"um"`, `"uh"`, `"like"`, `"you know"`, `"i mean"`), the extracted `word_obj.word` must be rigorously normalized [cite: 16, 24].

1.  **Whitespace stripping**: Whisper tokens frequently include a leading space (e.g., `" uh"`, `"you "`). These must be stripped via `.strip()` [cite: 24].
2.  **Lowercasing**: Whisper often capitalizes sentence starters and proper nouns, including the pronoun "I" and sentence-initial filler words ("Um", "Uh", "Like"). Complete lowercasing `.lower()` is necessary [cite: 24].
3.  **Punctuation stripping**: Words at the end of prosodic pauses or sentences will be appended with commas, periods, or question marks (e.g., `"uh,"`, `"like..."`). Regex or string translation tables must strip non-alphanumeric characters.

```python
import re

def normalize_word(word_str: str) -> str:
    # Lowercase and strip whitespace
    w = word_str.lower().strip()
    # Remove all standard punctuation
    w = re.sub(r'[^\w\s]', '', w)
    return w
```

### 3.2 Handling Whisper Artifacts and Disfluencies

Whisper exhibits specific behaviors when transcribing conversational speech:
*   **Variability in Filler spelling**: "Um" can be transcribed as "um", "umm", "hmm", "hm" [cite: 23, 24]. Your filler detection dictionary must account for these variations.
*   **Disfluency skipping**: Whisper is weakly supervised on web data, much of which features cleaned subtitles. Consequently, the model exhibits a strong bias toward omitting "um" and "uh" altogether, "correcting" the speech [cite: 3, 16]. 

**Decoding Settings to Prevent Skipping:**
To force Whisper to remain faithful to the raw acoustic signal and capture filler words, specific configuration thresholds must be adjusted during the `transcribe()` call [cite: 25, 26]:
*   `condition_on_previous_text=False`: Prevents the model from using the previous segment's text to predict the next segment. This minimizes hallucination loops and stops the model from prioritizing grammatically clean sentences over raw acoustic disfluencies [cite: 25, 27, 28].
*   `no_speech_threshold=0.6`: Standard default, but ensures that low-confidence breathing or background noise isn't erroneously parsed as a mumbled "uh" [cite: 27, 29].
*   `log_prob_threshold=-1.0`: Filters out low-confidence transcriptions. If Whisper is unsure whether a sound was a breath or "um", it assigns a low probability. Keeping this at `-1.0` ensures garbage predictions are discarded [cite: 27, 29].
*   `temperature=0.0`: Forces greedy decoding, reducing randomness and ensuring consistent extraction across identical runs [cite: 26, 28].

### 3.3 Sliding Window Logic for Multi-Word Phrases

Filler phrases such as `"you know"`, `"kind of"`, `"i mean"`, and `"i guess"` span multiple `Word` objects. Because word boundaries are distinct objects, standard string matching against the entire segment text destroys the exact word-level timestamp association. A sliding window (n-gram) algorithm over the sequence of word objects is required [cite: 24].

```python
def find_filler_phrases(word_objects: list, filler_phrases: set) -> list:
    """
    word_objects: list of dicts [{'text': 'you', 'start': 1.0, 'end': 1.2}, ...]
    filler_phrases: set of tuples e.g., {("um",), ("you", "know"), ("i", "mean")}
    """
    detected_clips = []
    
    # Pre-normalize the text for sequence matching
    normalized_words = [normalize_word(w['text']) for w in word_objects]
    
    max_phrase_len = max(len(phrase) for phrase in filler_phrases)
    num_words = len(normalized_words)
    
    i = 0
    while i < num_words:
        match_found = False
        
        # Check from largest possible phrase down to single words
        for window_size in range(min(max_phrase_len, num_words - i), 0, -1):
            window_tuple = tuple(normalized_words[i : i + window_size])
            
            if window_tuple in filler_phrases:
                # Calculate exact start and end of the multi-word phrase
                phrase_start = word_objects[i]['start']
                phrase_end = word_objects[i + window_size - 1]['end']
                
                detected_clips.append((phrase_start, phrase_end))
                
                # Advance pointer past the matched phrase
                i += window_size
                match_found = True
                break
                
        if not match_found:
            i += 1
            
    return detected_clips
```

---

## 5. Installation and Environment Constraints


The operational environment specifies a `python:3.12-slim` Docker image with `ffmpeg` pre-installed. This base image is a highly stripped-down Debian variant, necessitating careful management of Python dependencies.

### 5.1 Pip Packages and Dependencies

Because `faster-whisper` depends on `CTranslate2` rather than `torch`, the installation is dramatically smaller. A standard `torch` installation exceeds 2.5 GB, whereas `faster-whisper` and `CTranslate2` are an order of magnitude lighter (~100-200 MB), allowing the Docker image to remain slim and agile [cite: 2, 42].

The requisite `requirements.txt` should contain:
```text
faster-whisper==1.0.3   # Specific version pinning is recommended for production
```
Running `pip install faster-whisper` will automatically pull down `CTranslate2`, `tokenizers`, `huggingface-hub`, and `av` (a Pythonic binding for ffmpeg components, though we rely on subprocess for stability) [cite: 7, 9].

### 5.2 CPU Execution without CUDA

`faster-whisper` relies on CTranslate2, which has built-in support for Intel/AMD CPU architectures utilizing OpenBLAS, Intel MKL, or native SIMD instructions [cite: 11]. It works completely independently of CUDA drivers. When the container executes `WhisperModel(device="cpu", compute_type="int8")`, CTranslate2 seamlessly invokes its optimized CPU kernels [cite: 7, 9, 11]. There is no need to compile custom libraries or install heavy CUDA toolkits in the `3.12-slim` image [cite: 9].

---

## 6. Common Pitfalls and Mitigation Strategies


Deploying automated temporal segmentation utilities at scale reveals several critical edge cases. A robust module must account for the following recognized issues.

### 6.1 Hallucination on Silence

The most pervasive flaw in the Whisper architecture is its tendency to output phantom text—commonly repeating phrases or emitting arbitrary captions (e.g., "Thanks for watching!")—when encountering prolonged silence or non-speech background noise [cite: 23, 26]. 
**Mitigation:** `faster-whisper` incorporates the Silero Voice Activity Detection (VAD) model. By passing `vad_filter=True` into the `transcribe()` method, the audio is pre-processed; purely silent or non-vocal segments are completely bypassed by the Whisper decoder, definitively eradicating >90% of hallucination errors [cite: 12, 26, 43].

### 6.2 Timestamp Accuracy and Temporal Drift

Whisper's temporal resolution is natively constrained to 20-millisecond windows due to its convolutional sub-sampling layer (feature extractor) [cite: 3, 15]. 
*   **Word Boundaries**: The word boundaries provided by the DTW cross-attention algorithms are estimates. They are remarkably accurate for clear speech but can become "fuzzy" during rapid speech or overlapping dialogue [cite: 5, 23].
*   **Padding**: Because boundaries are not mathematically flawless, clipping video identically to the `[start, end]` tuples often cuts off the initial transient or trailing tail of the filler word utterance. Adding a static padding of **0.15s to 0.25s** to the start and end (as demonstrated in Section 4.1) is vital to ensure acoustic continuity [cite: 28].
*   **Drift**: Over exceedingly long files (e.g., >2 hours), internal timestamp drift can occur. The built-in Silero VAD segmentation in `faster-whisper` effectively acts as an algorithmic reset, breaking the audio into discrete chunks and preventing catastrophic temporal drift across long transcripts [cite: 25, 26].

### 6.3 Memory Saturation on CPU

Loading large neural networks into system RAM can trigger kernel Out-Of-Memory (OOM) killer processes in containerized environments.
*   The `large-v3` model requires approximately 3GB of RAM with `int8` quantization [cite: 11, 25].
*   The `small` model requires less than 1GB of RAM, making it perfectly suited for low-memory Docker instances while maintaining high temporal fidelity for disfluency capture [cite: 7, 11].

By strictly defining the `compute_type="int8"` and enforcing the `small.en` or `base.en` architectures, the module guarantees a highly scalable, stable execution profile that avoids container termination while providing rapid, accurate extraction of filler phrases.

**Sources:**
1. [ruslanmv.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHpZ53DCcqzOPPU850WLBmMmm8n84YFc5KpvOK0AG652Y0Bo6rstAuG64wt2zKgEY1TTLQgW66MhB_n0p-glYJdzc92QtzVNi8DDk-sKNA_3gxmDY2DiykAkf2Tm4mF4_sxJQAPkoUExfiMiQtGKZ2XzzE7WtAHe0L_odot5iAz7iGM5Q==)
2. [modal.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1KgBnDg6yhPNZVoZ3BNVLprp4QJvrSXwOYRkS48G2zTMCcfcYhBL-z9M9m79czxiV3FjXwjtmPWXNsPQybaGoXVvmR6FSIMQwhsItrt0PAcn4s4wD3nQeJLONDrn2GCbed8vJI14=)
3. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZPQTEfZSs-5QG-0Z5y926DTgDl5tmxH0zNxDpUIwWHfGQTqc02M37ToTZ_DD2PoO4ud3nOUC6S9N40h7DKUhnTAvF4j0IZmjXVchi24Kgfu6DigOlJeYspC-NZV_YDWRBmrvcbIB45tsAMkRfOS57ZGF1xBbQLiDn6EXv_zV4SYdIOkjjOAVlg6n0GpQOViQTwwZssv6eyCmARggT)
4. [aimodels.fyi](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEaCwKQf8BUWbfGJ-ExZmPln-DM8C3QoOVVke1wH63c1LjGkk2pDDg7nPNstAJXTckYOZWMT2OXQ2mdRROwZ-ZdhsMlv4EKhUwLq4tX5E46pmDCLsK1-cEVWD7JcrI0GdxgYcy6sKc6zpTTXEkvgoSiB2p49gtAJSY_0aYo)
5. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE146xQOrStrv1_0_49QjJPPAJGg8aKNb29D9o-mGHCfgHb2lM8N19Wsn1PAWZopSca8_-ZUF5uExQvpUJVWV04nU-nx7OxfViCo0UOBN0lXeNN9UFn6_5e3YjfNgyeS-qIJ8Bb-E858HK3KIvTecKPRnvC)
6. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFTwrocwP-lYd1QJsfpkYw8r2H0aBtY4kCmPWgzwR5p2uJvvuAgYCULoMgB0MSxDVVqB163IS6eR7lt-5o9TZgyYf_MiEHhPJiqq7IZTYdyI9FdeoJID5lrGGE_3ZRIRg1g8fjvnecKUY9_dcsUkKUKimg=)
7. [linuxcommandlibrary.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFXqA5P10W93NzQfwj9DN_dzOYkAE7LugPb457JOeqn3o0cCdi9TimGLvoNC248P5b0yfAuBBuvT60nYiSR2ZoljZZ0xYp2CC6xyVxSmLe6Jyg7iAgcoYWW56orsrnvcqly__X2-6Uj7Q==)
8. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGdkCihDy3UjTxZxqQLGjKZV_MiNiFw4aM-BukgmydOUhwJXvmUTjsfRZDRQQ0930LKZ5mMjCUzz3Jr2rk9KxITIZV5r7PHM2X49RduUiLnQW0K1Yphjq_jCGMD68qVejHhKLkfx-07wV4JMFqDEAqwZ0OOyiM=)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAvtAbIwrN3TRz4ksw9toVl76FNZUcvMAB2kkx46C_RtdoxcdEevherVD1QA-9X5psDXDC4g8X9OIWtH1JebvaJ49n6jqtvvY0o9sindlRsPybYgazSMxS4IfS2LNURQ==)
10. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_pfGDzeMZayUhNlbjWMqec9tcsRijX0YiinRl8BNu-2Xj-OfRAGFxs9G4xhmQ6YX626HxNfM6SczBtP5yR_KTVCg3iy6EzFi2nfHgrRxzrp0kiCf9SptkMqJ8gpDN9HUorHYVCILUMMuWAggRXFhRbictsMajEmCm1krRCICV7qJw6yAAhO9SqbMyKHR-KpcQM-t7jMMn-cgGnwSqIvqLocdQx63DlyiMGTcSDCAYQw==)
11. [localaimaster.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEkbmUW0uxv2Z5Z15VCtodqs_tFM1K9EuHtJ_wHxrUd_Jp2E2XxJuUkRVnRfQVkoN4lRjtZbM6I5ncNGjVBHBDOyVoktbfiSNYG6_Pn-44oAvUZiLAbMfESSQpc1Yo2vhaEYcLy8rLUd5E=)
12. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG8DfTlDIN_8FLY2X4hKHy6VjfWnuKMG1o7S-cxWIAFB9O0jxl9M7jmNAz4IylnCp_7pq3lL5VyLmYr27nOGEKSsQ4pokb_g6PUNN9Amw6IPFJ-6EL-45ohhmt_mqAVfwB6JphZCBjveIkEsw70)
13. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEKRhSzvx6uZ4c9dAC5fnxcB43UFmY9VT3RuoqOeBVwbRQnBhK1daaQEm9iFU0VcYYgIzlKROraCnUZmxPx6i-EdTpyesBSIBnV67emjBQFce32zyhhgoYB59tH)
14. [racedorsey.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjUOi3odMXn59_fHIhmlFfjBJW3ccJxpqar7LDcymu0pE_U6pTAz6A6ZstE8sT2QQK2o6govcooXhUWpp9eGuGu0UgB1ANqCsB89bD2dt8aAeLo0p9ph8Lrg2YjRQERZZAUKrhHpBdg-JuRcot7ku4uXh0uRBed0E=)
15. [r-project.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFHL4grkCnLtyR4jTmrus0NHSpBcScRiLuJOEiIUj8qP8NJ08i6wQ19psvVknwSx64fUBO4GWfdRiWpxQK1wH5nSK8YIsC6aID5Pa34D5JCG-AmdNfaDvN-r-3A1x0L2F3Dip2tK0mgohqvKK4AdhQbg==)
16. [guptadeepak.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFtCLxfTVQIkMcJDKd7oC9jh1LYVyeSmk7sEODzcGoC2k7Z1Q3MRsvVM7M4ldPIYRROx2enFU8MVuhjN1nf8QGiJIfB6QRxnV2h-FFpZ_hHHPtOMqs-ok9O2yXzNkqLkqirhChTeH30DugbW73VudExKxNZcyMn)
17. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCxMgqY2i_lxd57HjcKc7Ajh57BWui9Ph-repC5gh1-EXC774ub39hcaNuBXp-xCe4EnFCOLaFrGcGzaai4RjmH9FLIitUilxzgTtuuiafauPhQgtcPHk9t_mV7GQisURPHff0b0CmA6R3HK7wTaQ=)
18. [thepythoncode.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElSS0zyeKFkLC4azhp9U0IQ3fz8ZR3th4N_oblZlA6nGxaw_7-Wcjah7WUB0q5suqVTeQe2gpc544XBTrEBHjhxi3sMG1kO3dzqSU7N8Xz23GLfzJPt-m5cWgKCw7AuNThN3Qputq1U_0EZuz0HQIwY5qyeILBfGxcTw==)
19. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUurlH1IuRxZz1I8MrMXs28P_04CPkRTSEIxZwoWhDtDsDGYnFfUtFHmcMRXhsXGyyCUaWPo240B6P5FejwwGe4jTgKbwG1ZKNrI2yG-ZnkDxMT_BnBj8ZLaZHp0zBYij7xX9I5J93W9y-eBak2ISAhW49Fc_AeNOZAoIShIwFZ2MT1noAbJLWaVCZWkNcn4xoutgUI_v0)
20. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwPiDLchtX6CnXAju-T-vIsPtYjMM415tig48IbUFonaXDwW89zg2nYjHJHiiJcj3poI4GXRRk7FO5OL5WURDSGoge9GvUTPPloEAxa-S_q8iIU-ADhAUpKZGobXjt7IWQ2oxG3dFT8xcXbio4aA==)
21. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGyL5hJarBz0brnLOPJBX-NClaKYfPTdpdR2F7In_UI55mEmy82NSrJUTiYxU5O2VY_3nGNk-0qebcYGhW2Rj0_Qrysjzcchp3JY6D8o9XlBHZNUIGOCi6w1MY9OEp7s0fkFV8k2dZeOXEwqeTtapFvTaui7bTt91nLTBbWznYvnjQ-umRmFcF4tXh5pcBDWg==)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoNK1SS6RLbAH-pMNVyaSBQ0MfnvJ_BnIHb26Z0TzHdDAZBP6vfWlUkiTD2cTn8TgICLa6Yq4H2RZqB3gebSidKX1QvLvoAgG-0SUFkAxQUkiNIMwj77JNDWBz2l6taqWVGub4rfOteE7r6o14o_rz-W66PKlVxtV_DaEfAPO6u3axfQrl5wDarzLuDRcvOd1LcDhLeP8zs_SFTDNuRw==)
23. [plainenglish.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2Tm29JJMZCu5xBgRP75GYbo2ikMaWdEDTLgabMY3yb1FvBtCwDH03s9greo5GQc26KPZi6RDe_43kpD_pfXhlEy_uyIWym12WZmgfbT2Es6ykYaA4821ZuMImkSSl_g8mXyxf7_3VhDTs_pJ4fv0vxN-lx213b_cGqPDx3CGegAwV3wWPd3VaY1wTynCwFIpoydIdNjMYciywnBpe2nnWog==)
24. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwcWk7UBtwmv6r_q3RKAP3JZb0tFWqsPE_kcbZ8IBF3jb5QGxDIgVZ6oBJ9wEZCw4rKFdMK4bgvdu3HlF_IzRrp-dZIogqqh4JSsz8OK3sJ9YGhGKafgAGEBUNnbJGUNb1JBnpvA11Sb3AkvY-4blH-K-3euOUn3hscgSu8q1ilTXZ7YQon3uNX4jTDZlY4MXaNvi6OdC01oZdtSpyfDbKGofO0sFKLHmL3D0mP9fCONoK5clhwLED74u4BxJz)
25. [spheron.network](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOhOPH1vIb9s6-iaPg5G6BdtU2itMDtuqiCGP0evrEflUZBQ3LzMT_RPm-SpXon0FrHAKEfYyBEBccmaI9szq_bCUv7rBMiG2dzWnR4autUP1Mab7Xge_xPpdUQWMtnpXJAJYzfxydct3cvwBFjYBvMY7Zp9-C3r_DGcOG-bqbafs=)
26. [plainenglish.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEkithC5ItOYInc1rmXl1DGCU7kMmt1WMCWO9bCQnsVZ8z52K2fhiNxDxikOS9iOfkByLg3kmDiSR5kWPZpSbn6pvmWJKB9wLVbXpewor_1C8up4_6VLBM_k-0IElykmVWCeGGmfmKs_mmVYNy85PjIeQKkyzOv_QRPzjOi)
27. [cloudflare.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHibzIsRLZCkyzbqseJE_4tdxwrTNCpD_1y5rUmzYS8z2id4K1rpX7lfRuXLU_ZrSP9TNCCF9BRjTaJT16ulHvLLWbMJ9edUXoP-XpJd8otpurU-lwGpFQgvcJ5SiMroA0YBeArJJFtkPY5LHvLxA0KLfK5JPNdABRrXuc3Ow7LY84=)
28. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHAkkC9abzAw-6DKPO7HsDDPxoQf3akPE8Zm_reTjcvcNvt5CqitaK63mlba9fEDTm_adCueLACvzlByKoQJUknR1yPP84p1nrldVIj_6tPsZ7TQXvdHBbaxydoPkUiPaWbBYN4r1i9qI5aaapbpesKTjkE-YneV-hF8gimoeXLFfsGBGK2IJ6IH75JgWE3PGfZdQ==)
29. [whisper-api.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7E4khROTxVlDBhv4wWLBWsu-K-7is1UaG3aB7WHtPFNS8FyTmWbYeReFCsjg9qJBw6AkopqtU8EH_JneWzM0PLJFy5TGH_styLyTsOvGAlhgtV8iCsYNbL7Uhwk3Be3FdL5TqDiigySo=)
30. [mux.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEXMWUHvNglzwjyTlgcDnWtGP-JZmZf8w5Zbtr6YZIA3mzJKcjMw15GFhIoNJ0WRfUG-wLVJlvEiNlVdYD0DgYnIzwQxiSgenDPzITmxIIqEl3NTo5en_QR3uZlzKyZj7OdtguzHl46jt3bJhmVxEN90VdfJqz-Bw==)
31. [ffmpeg.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFiNBXQEgu9wrWsEulBXuym1nLWee8w_fuASIf5-tEUCM9IgVNEQybx_mjjMtZLT6pQsrhS_uAgFgOrQ5vwpfCCen88YDwU-_wcdFK3VZSNFWPqZ_roH0PwOnU=)
32. [wavespeed.ai](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFj8fmt4xsJFSr8JTBkioJyXtc_-2uIkvunR2I-RIF0VYZzkJlwhFM7w6h8I5y3LNyERmYrsiS-J3OmVH8gC02l60zV-1NDY9R4v8P0PUPhMhjJNiDqk1cydmv_DTEtyDeD80OwRN2BbMB4_kKd-6SpWYmqlBMQJiTxuNIpe_K7jByf70e9ODBuVY5q5Q==)
33. [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGL-rJFIFni7axZ46E_3tcCxDcJqECmUxx4naUitEnbQOD7UKiHqDhNOfkLKykNpjFKAOUZwzDV98dXPbEq0ebI0rbqoqceW7HvhoeztNaUpDkgPTH_KFFf1gQvTNhWhq1L)
34. [cloudinary.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnGphO61cdki9GxldR5Dtc4N0cM9aX2KY7RgWI_-4xG15SVDB6BJPmfdVCZZfNyRFAr1Rjq4E-49TifSQ-eZ5UlEXvDj2Yfup3mx6Kfr8xaXYqSrG9v2b4Z63zJQDh7blHkgr0oVLNJuui9TyiXsy0ugGf2AoeWRxHRiU7XDBblJnM)
35. [superuser.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1M182CV4lK2o82Dg1VJokTPI6IX7CjofBYcVt53zxaZMPTRxwJyxbrggjCQjKvq20YqjOKc_bT5mw73tT2dROaTCWHy9P3t1DET1QgNKdt7ZMrehLhKnNDCaQC0d2Tyc2wD0ph-Rwdz84GbCHLn7fBC1QmosYLCb8GAoE)
36. [superuser.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFi2EYzJgJTDCGHyIgMXAqdo-Q7PKJ-TPG9X7QMxGVImGMhVobbWr44voocr1enwXDcfN3GOwVDRqUPrEJgxLERZ5SMeag0NIeAJFTfh07OhChwREdG12MpY9gPbzmU6n4GWr5KzWhiEl7SVIIWMCWJa2zX)
37. [ffmpeg.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEaTXWoDu4F8LP_Kwb_5NRFVsIuDQw14SNmB-5CaV7uw5d8ogGBCGM7RlWvKtI8FZYWd8JbGpui3DZznLXeSEoHL9HrNawAI0XhkQdutGTKew_ao6K79n8E9i0czBcJ)
38. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFen0QdGxyqmovvVvk3_OGEeh2ds1cEdjnxw3okzReXnNmnB57aD59nEAhxmkh7iAJvhUD84EuYJ6BhzuEZ8OMZyhyFCXAglanTdkKBlQUrecWLFwaZ7XW1PmI6XAImsLoqlxFmn1NP15tWZ2mx5pxzBzsrWS85uwQV)
39. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEdrcb9-JNIaT_G77F-BuJxQAqJZ2kutYRlMBvg9NXLyEU-W4rWZh1FWXn3EL3THs6Qz3hFvC0XAnxVJVg-t4xjO1fboRI-yfs9eeCkPVegeGBQP9EF6JJfVxTJ22WFNaYfbfNraJhCgmvwRGpyCj2x79mnVVwdw8KOJEV1YmebjD9Ry_e5m7mqgipYA==)
40. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGC4pxWHgXRkf1Ev6RjIZjhC8fZ4wuL05Vz3Tm7wKubW6rpoJzb8OX1YsT0ey4A5-0FzcW5pUfQWv2BglD-jX2o1qAS56WnNejG50FUwEUY1QY56Ayjn-x09qr4ry2z6IUxkA3IP_Hzk6MdAQWC785tFLyizl2OukAAjE57Gfu691LCk_3BuxxSrWc1x2h0Wn2NDHqbSp2thwzkV0e7EP4=)
41. [quora.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaYYYphsJVfXlJ8RqpV0uJgwb0dW9O30uwIFyD7TSKpb0xaob-weWzH7hOma3d2RhPMQTs2mnAIJvDyZk4KZx414ujTvkuVHq8izJOVHsP5wvluq15AQe9U7-cL2lRv5EzZPBc3fdx6f-xcQ7pQnchFMi40N0-eKh25OomRw-T5yvx6fNbqmmyH7lv9RCScXGDRSbQqYJA4hSxNdklVRoqyGd_XPg4IJaEH4_r64PYNWo3pHxIYc8iPPkkl8iI5Tn-A4xp1HeylmXUAV9_zrUopD35nZWe5eVitv7B3W_V)
42. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFF3GP-XTxcM6mmoLVrOI_84oSM2blVIbF6mh3BSbLmb_sH24Gh9jOnMQCWrHgrjJ4_Pb1dcsKYU_vu8xw_VgQD7Iqw2BB1piNPX14oIJ7Rrnk5JL9gA3zRdw==)
43. [tessl.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUBxvTPobX8dFTQhHsGQI3ZlzBDvp55DPevG8Q6IIpE2uFKbvGjf8m9Vlp-jtXEMUizfsSC_Nkefubdot0TefZ-9s88b5MA8Gsv2uEpNMQ9R_-R7irXnnAFoes1Yv4EoMFbSqMqU5oBHXaVBvO3mAU3Y2NRUCwkactVvOWezoe8-_Au3qsGC13ZriHTw7mUlw=)