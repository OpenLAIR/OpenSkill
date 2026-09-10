# Domain Reference for evo-audio-transcription

**Responsibility**: Audio extraction from video containers (FFmpeg subprocess), Whisper model loading and transcription with optimal parameters (word_timestamps, condition_on_previous_text, language, no_speech_threshold), returning structured transcript data with word-level timestamps.

**Key functions to implement**: extract_audio_from_video, transcribe_audio, get_all_words_with_timestamps

---

## 1. Whisper Transcription API and Timestamp Mechanics


The core engine for transcribing tutorial audio is the OpenAI Whisper library. Whisper is a general-purpose speech recognition model built upon a Transformer sequence-to-sequence architecture, trained on a large dataset of diverse multilingual audio [cite: 1, 2].

### 1.1 Loading the Model and Available Models

The API provides a straightforward mechanism to list and instantiate model checkpoints. To verify available models, the `whisper.available_models()` function returns a list of official model names [cite: 3, 4]. This includes varying parameter sizes: `['tiny.en', 'tiny', 'base.en', 'base', 'small.en', 'small', 'medium.en', 'medium', 'large-v1', 'large-v2', 'large', 'large-v3']` [cite: 3]. 

To initialize the model, the `whisper.load_model()` function is utilized:
```python
import whisper
model = whisper.load_model("base")
```
When invoked, this function downloads the PyTorch state dictionary into `~/.cache/whisper` and loads the model into the specified device (CPU or GPU) [cite: 3, 5]. For english-only tutorial videos, utilizing models with the `.en` suffix (e.g., `tiny.en` or `base.en`) generally yields better performance and reduces the memory footprint compared to multilingual counterparts [cite: 3].

### 1.2 The `transcribe` Method and Parameter Optimization

The primary inference function is `model.transcribe()`. To achieve accurate timestamps and high-quality transcription, several parameters must be carefully orchestrated [cite: 5, 6].

**Table 1: Key Parameters for `model.transcribe()`**

| Parameter | Type | Default | Impact on Transcription and Timestamps |
| :--- | :--- | :--- | :--- |
| `audio` | `str` or `np.ndarray` | Required | Path to the audio file or a pre-loaded NumPy array of audio data. |
| `word_timestamps` | `bool` | `False` | When `True`, utilizes Dynamic Time Warping (DTW) on cross-attention weights to extract word-level timestamps [cite: 5, 7]. |
| `condition_on_previous_text` | `bool` | `True` | If `True`, feeds the previous transcript segment as a prompt for the next window. If `False`, decodes independently, which reduces hallucination loops [cite: 5, 8]. |
| `language` | `str` | `None` | Setting explicitly (e.g., `"en"`) bypasses automatic language detection, saving compute time and preventing incorrect language shifts [cite: 6, 9]. |
| `temperature` | `float` or `tuple` | `(0.0, 0.2, ...)` | Defines the sampling temperature. Lower values (`0.0`) are more deterministic, ideal for clear tutorials [cite: 5, 6]. |
| `no_speech_threshold` | `float` | `0.6` | Threshold for silencing probability. Higher values make the model more likely to categorize audio as non-speech, reducing noise transcription [cite: 5, 10]. |

**Optimizing `word_timestamps=True`**
Natively, Whisper does not predict word-level timestamps; it outputs phrase-level segments representing 30-second audio windows. Passing `word_timestamps=True` employs an inference-time algorithmic trick: it applies dynamic time warping (DTW) over the decoder's cross-attention matrices to align the predicted byte-pair encoding (BPE) tokens with the acoustic Mel-spectrogram features [cite: 7, 11]. This dramatically improves the precision of time boundaries, though pauses between words can occasionally inflate duration values [cite: 7].

**Understanding `condition_on_previous_text`**
For long audio tutorials, Whisper is notorious for falling into failure loops where it repeats the same phrase endlessly (hallucinations) [cite: 5, 12]. The parameter `condition_on_previous_text` controls whether the text generated in the previous 30-second window is passed as a text prompt into the next. While `True` aids in preserving context across window boundaries, disabling it (`False`) isolates each 30-second chunk. Evidence indicates that setting this to `False` significantly improves robustness against timestamp drift and hallucination loops in long files [cite: 5, 8].

### 1.3 Return Structure of `model.transcribe()`

The output of `model.transcribe()` is a highly structured Python dictionary. The timestamps returned within this structure are always represented as floating-point numbers representing seconds (e.g., `12.45`) [cite: 13].

The dictionary contains the following primary keys:
*   `text` (`str`): The complete combined transcription text.
*   `language` (`str`): The detected or specified language code.
*   `segments` (`list` of `dict`): A list of segment-level dictionaries.

When `word_timestamps=True` is provided, each segment dictionary in the `segments` list contains the following granular schema [cite: 5, 14]:

```python
{
    "id": 0,                    # Integer ID of the segment
    "seek": 0,                  # Seek point in the audio stream
    "start": 0.0,               # Start time of the segment in seconds (float)
    "end": 4.5,                 # End time of the segment in seconds (float)
    "text": " Welcome to the tutorial.", # Text of the segment
    "tokens": [50364, 4324, ...], # List of BPE token IDs
    "temperature": 0.0,         # Temperature used for decoding
    "avg_logprob": -0.23,       # Average log probability of the generated tokens
    "compression_ratio": 1.2,   # Gzip compression ratio of the text (anomaly detection)
    "no_speech_prob": 0.01,     # Probability that the segment contains no speech
    "words": [                  # Present ONLY if word_timestamps=True
        {
            "word": " Welcome",
            "start": 0.0,
            "end": 0.8,
            "probability": 0.99
        },
        # ... subsequent words
    ]
}
```

### 1.4 Model Selection: "Tiny" vs. Larger Models

The Whisper architecture scales from the `tiny` model (~39M parameters) to the `large` model (~1550M parameters) [cite: 2, 3]. The `tiny` model processes audio exceptionally fast, operating in real-time or faster on standard CPUs [cite: 15]. However, for the specific task of timestamp accuracy and chapter boundary detection, the `tiny` model exhibits broader error margins and is highly susceptible to timestamp drift [cite: 16, 17, 18]. The internal cross-attention mechanisms in the `tiny` model have less resolution to map tokens back to acoustic frames accurately. 

To achieve optimal timestamp alignment for chapter transitions without overwhelming system memory, the `base.en` or `small.en` models offer the most optimal trade-off [cite: 6, 9].

---

## 2. FFmpeg Audio Extraction from MP4 Containers


Whisper performs its own internal audio preprocessing, converting inputs to a 16 kHz sample rate, mono channel array before computing the log-Mel spectrogram [cite: 19, 20]. However, feeding a full HD MP4 video directly into Whisper's Python API requires `ffmpeg` to parse the video dynamically in the background, which is computationally expensive and memory-intensive for large 23+ minute files [cite: 21].

It is highly recommended to proactively extract and normalize the audio using an explicit `subprocess` call to FFmpeg.

### 2.1 Optimal FFmpeg Parameters

To extract audio optimized for Whisper, we must strip the video stream and force the audio into a single-channel, 16,000 Hz, 16-bit PCM WAV format [cite: 19, 22]. 

The exact optimal command line structure is:
```bash
ffmpeg -y -i input.mp4 -vn -acodec pcm_s16le -ac 1 -ar 16000 output.wav
```
**Parameter Breakdown:**
*   `-y`: Overwrite output files without prompting [cite: 16, 19].
*   `-i input.mp4`: Specifies the input video file [cite: 16, 20].
*   `-vn`: Disables video processing, extracting only the audio track [cite: 19, 23].
*   `-acodec pcm_s16le`: Enforces the uncompressed 16-bit little-endian PCM codec [cite: 19, 22].
*   `-ac 1`: Mixes the audio down to 1 channel (mono) [cite: 19, 22].
*   `-ar 16000`: Sets the audio sampling rate to 16,000 Hz (16 kHz) [cite: 19, 23].

### 2.2 Python Subprocess Implementation

Implementing this within a Python skill module utilizes the `subprocess` module. We utilize `subprocess.run` to capture standard output and ensure the operation completes synchronously before Whisper attempts to load the file.

```python
import subprocess
import os

def extract_audio_for_whisper(video_path: str, output_wav_path: str) -> bool:
    """
    Extracts 16kHz mono audio from a video file suitable for Whisper transcription.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    command = [
        "ffmpeg",
        "-y",                   # Overwrite existing files
        "-i", video_path,       # Input file
        "-vn",                  # No video
        "-acodec", "pcm_s16le", # PCM 16-bit codec
        "-ac", "1",             # Mono channel
        "-ar", "16000",         # 16 kHz sample rate
        output_wav_path
    ]

    try:
        # Run subprocess and capture errors
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"FFmpeg Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Failed to execute FFmpeg: {e}")
        return False
```

---

## 3. Whisper Segment Timestamp Accuracy and Alignment



### 3.1 Known Issues with Timestamp Drift

A well-documented phenomenon when using Whisper on long-form audio (such as a 23-minute tutorial) is "transcription drift" [cite: 18, 24]. The native model predicts timestamps as distinct tokens within its BPE vocabulary (e.g., `<|0.00|>` to `<|30.00|>`). Because Whisper transcribes in fixed 30-second sliding windows, any minor misalignment in the acoustic boundaries of one window forces the next window to seek slightly off-target [cite: 18, 24]. 

Over twenty minutes, an error margin of a few milliseconds per window accumulates, resulting in timestamps that can be several seconds out of sync with the actual spoken word [cite: 17]. Furthermore, background noise or extended silences overwhelm the sequence-to-sequence model, causing it to hallucinate timestamps [cite: 11, 18].

### 3.2 Mitigation Strategies

To improve alignment and arrest timestamp drift, several techniques should be applied programmatically:

1.  **Enable Word-Level Timestamps**: As noted, `word_timestamps=True` bypasses the pure token-prediction timestamps, utilizing a cross-attention Dynamic Time Warping (DTW) matrix to map tokens to the audio waveform [cite: 7, 11]. This anchors the timestamps to physical audio events, significantly preventing cumulative drift.
2.  **Disable Prompting**: Setting `condition_on_previous_text=False` effectively breaks the dependency chain between 30-second windows [cite: 5, 12]. While this may cause slight variations in spelling for proper nouns across windows, it prevents the model from dragging timing errors forward.
3.  **VAD Filtering (Advanced)**: Utilizing an external Voice Activity Detection (VAD) algorithm to cut the audio file on silent boundaries before feeding it to Whisper (a strategy employed by tools like `faster-whisper` and `WhisperX`) is the most robust solution for severe drift [cite: 11, 14]. However, for a self-contained API, configuring `no_speech_threshold=0.6` helps the native Whisper model ignore silent regions appropriately [cite: 5, 6].

---

## 6. Common Pitfalls and Edge Cases


When deploying this pipeline, several engineering pitfalls frequently occur:

1.  **Package Versioning Check**: The query asks if `whisper.load_model('tiny')` works with `openai-whisper==20250625`. Yes, the `20250625` build is an official, recent PyPI release of OpenAI Whisper, and the core API signature `whisper.load_model()` remains unchanged and fully backward compatible [cite: 2, 34].
2.  **Memory Constraints for 23-Minute Videos**: Transcribing 23 minutes of audio requires the entire Mel-spectrogram to be processed in chunks. While CPU processing uses standard RAM, passing `fp16=False` is necessary on CPUs to avoid warnings [cite: 3]. If running on a GPU, a 23-minute transcription with the `medium` or `large` model can trigger Out-Of-Memory (OOM) errors on lower-tier hardware (e.g., < 8GB VRAM). The `base` model typically consumes around ~1GB of VRAM and scales safely [cite: 2, 3].
3.  **Silence and Music Hallucinations**: As discussed, non-speech segments cause the model to guess tokens [cite: 18]. If a tutorial has a 2-minute musical intro, Whisper might aggressively transcribe phantom text. Utilizing `no_speech_threshold=0.6` helps, but users may need to increase this to `0.8` if phantom text persists [cite: 5, 10].
4.  **Floating Point Timestamps**: All time metrics in Whisper (`start`, `end`) are Python `float` objects denoting seconds [cite: 13, 14]. Caution must be exercised when converting these floats to integers or strings, as precision errors accumulate. Always maintain floats until the final formatting stage.

---