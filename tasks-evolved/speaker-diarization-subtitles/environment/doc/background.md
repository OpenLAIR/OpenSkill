# Comprehensive Guide to Building a Speaker Diarization and Transcription Pipeline

**Key Points:**
*   **Pipeline Architecture:** Building a robust speaker diarization and transcription pipeline requires modular integration of Voice Activity Detection (VAD), speaker embedding extraction, hierarchical clustering, and Automatic Speech Recognition (ASR).
*   **Library Ecosystem:** Modern implementations rely heavily on specific library versions to avoid breaking API changes. This pipeline is anchored on Python 3.11 using `speechbrain==1.0.3`, `openai-whisper==20231117`, `pyannote.core==5.0.0`, `silero-vad==6.2.0`, and `torch==2.2.0`.
*   **VAD Shift:** The `silero-vad` package (v6.2.0) has shifted away from the legacy `torch.hub.load()` mechanism to a direct import module (`load_silero_vad`), significantly streamlining its integration [cite: 1, 2, 3]. 
*   **Embedding and ASR:** SpeechBrain's ECAPA-TDNN framework is utilized for extracting highly robust, time-invariant speaker embeddings [cite: 4, 5], while OpenAI Whisper (`large-v3`) handles transcription and word-level alignment via cross-attention timestamp generation [cite: 6].
*   **Output Formatting:** Complex output modalities—such as Rich Transcription Time Marked (RTTM) files and Advanced SubStation Alpha (ASS) subtitles—require careful manipulation of temporal boundaries (e.g., converting floating-point seconds to centiseconds) and label mapping logic to ensure downstream compatibility [cite: 7, 8, 9].

Research suggests that aligning word-level ASR transcripts with diarized speaker segments via intersection-over-union (IoU) overlap metrics yields the highest fidelity in multi-speaker environments. However, processing large audio files on CPU architectures introduces substantial memory constraints and computational bottlenecks, necessitating aggressive audio chunking and stateful memory management. 

---

## 1. Audio Preprocessing and FFmpeg Extraction

The foundational step of any sophisticated speech processing pipeline is standardizing the input audio. Deep learning models for speech, particularly those within the SpeechBrain and Whisper ecosystems, are highly sensitive to sampling rates and channel configurations. 

### 1.1 Audio Format Requirements
SpeechBrain's embedding extraction models (e.g., `spkrec-ecapa-voxceleb`) and VAD models (e.g., `vad-crdnn-libriparty`) are pre-trained on specific acoustic conditions. The expected input is strictly a **16 kHz, single-channel (mono), 16-bit PCM** representation [cite: 10, 11]. Whisper similarly resamples audio to 16 kHz internally, but providing it pre-processed audio minimizes computational overhead. 

### 1.2 FFmpeg Extraction Command
To extract audio from an MP4 video file and convert it into the precise WAV format required by the pipeline, `ffmpeg` is invoked. The exact command is as follows:

```bash
ffmpeg -y -i input_video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 standardized_audio.wav
```

**Parameter Breakdown:**
*   `-y`: Overwrite output files without asking.
*   `-i input_video.mp4`: Specifies the input video file.
*   `-vn`: Disables video processing, ensuring only audio is extracted.
*   `-acodec pcm_s16le`: Sets the audio codec to Pulse-Code Modulation (PCM), signed 16-bit little-endian. This is the uncompressed standard required by `torchaudio.load`.
*   `-ar 16000`: Sets the audio sampling rate to 16,000 Hz.
*   `-ac 1`: Downmixes the audio to 1 channel (mono).

This step is critical; omitting the downmix step (`-ac 1`) on stereo audio will result in a tensor of shape `(2, time)` when loaded into PyTorch, which will trigger dimensionality exceptions in models expecting `(batch, time)` where batch elements are 1D audio sequences.

---

## 2. Voice Activity Detection (VAD) Mechanisms

Voice Activity Detection is paramount in diarization; passing silent segments to an embedding model generates noise clusters, and passing silence to Whisper can cause severe hallucinations. We evaluate two options: Silero VAD and SpeechBrain VAD.

### 2.1 Silero VAD (v6.2.0) API and Implementation
Silero VAD has undergone significant API refactoring. Earlier iterations relied on `torch.hub.load(repo_or_dir='snakers4/silero-vad', ...)` [cite: 12]. As of version 6.2.0, the model is available as a standalone PyPI package, eliminating reliance on PyTorch Hub [cite: 1, 2].

**Exact Import Path and Signature:**
```python
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
```
*Note: The `collect_chunks` utility is generally used to splice audio together, but for diarization, it is better to maintain the original temporal timeline.*

**Loading the Model and Running Inference:**
```python
# 1. Load the model (CPU is default)
model = load_silero_vad(onnx=False) # onnx=True is supported if onnxruntime is installed [cite: 13]

# 2. Read audio (returns a 1D torch.Tensor)
wav = read_audio('standardized_audio.wav')

# 3. Extract speech timestamps
speech_timestamps = get_speech_timestamps(
    wav, 
    model, 
    sampling_rate=16000, 
    return_seconds=True, 
    threshold=0.5, 
    min_speech_duration_ms=250, 
    min_silence_duration_ms=100
)
```

**Parameters and Defaults for Diarization:**
*   `threshold` (float): The probability threshold (0 to 1). A value of `0.5` is an excellent default for most datasets [cite: 14]. Lowering it increases recall (catches breathy speech) but decreases precision.
*   `min_speech_duration_ms` (int): Prevents transient noises (clicks, coughs) from being flagged as speech. `250` ms is highly recommended for diarization [cite: 14], as speaker embeddings require at least ~0.5 to 1 second of speech to be reliable.
*   `min_silence_duration_ms` (int): The duration of silence required to split a speech segment. Setting this to `100` to `300` ms is ideal; it bridges small intra-word pauses while splitting true speaker turns.

The output `speech_timestamps` is a list of dictionaries: `[{'start': 1.2, 'end': 4.5}, ...]`.

### 2.2 SpeechBrain VAD (`vad-crdnn-libriparty` v1.0.3)
Alternatively, SpeechBrain provides a Convolutional Recurrent Deep Neural Network (CRDNN) trained on Libriparty [cite: 10, 15]. 

**Exact API for v1.0.3:**
```python
from speechbrain.inference.VAD import VAD
import torchaudio

# Load the CRDNN VAD
vad_model = VAD.from_hparams(
    source="speechbrain/vad-crdnn-libriparty", 
    savedir="/tmp/speechbrain_vad",
    run_opts={"device": "cpu"}
)
```

**Extracting Boundaries:**
SpeechBrain offers `get_speech_segments(audio_file)` which computes boundaries based on thresholding the frame-level posterior probabilities [cite: 16].
```python
boundaries = vad_model.get_speech_segments("standardized_audio.wav")
# Output: torch.Tensor of shape (N, 2) containing start/end boundaries in seconds.
```
For more granular control, one can use `get_speech_prob_file()` which outputs the raw frame-level probabilities, enabling dynamic thresholding [cite: 16]. However, Silero VAD is generally preferred for CPU inference due to its highly optimized JIT execution (processing 30ms chunks in <1ms) [cite: 2].

---

## 3. SpeechBrain 1.0.3 Speaker Embedding Extraction

To identify *who* is speaking, we map audio segments to a high-dimensional continuous vector space. SpeechBrain implements ECAPA-TDNN (Emphasized Channel Attention, Propagation, and Aggregation in Time-Delay Neural Networks) [cite: 5]. ECAPA-TDNN utilizes attentive statistical pooling to capture global speaker characteristics [cite: 4, 5].

**Exact Import and Model Loading:**
The class `EncoderClassifier` is the canonical entry point in v1.0.3 [cite: 5, 11, 17].
```python
from speechbrain.inference.speaker import EncoderClassifier

classifier = EncoderClassifier.from_hparams(
    source='speechbrain/spkrec-ecapa-voxceleb', 
    savedir='/tmp/speechbrain_encoder',
    run_opts={"device": "cpu"}
)
```

**The `encode_batch` Signature and Tensor Requirements:**
The method signature is `encode_batch(wavs, wav_lens=None)` [cite: 11, 18]. 
*   **Tensor Shape:** It expects `wavs` to be a PyTorch Tensor of shape `(batch, time)` [cite: 11]. For a single audio segment, the shape must be `(1, time)`.
*   **Sample Rate:** Strictly 16,000 Hz [cite: 11].
*   **Normalization:** Manual normalization is *not* strictly required before calling `encode_batch`. The SpeechBrain module pipeline inherently includes a `mean_var_norm` step and `compute_features` (Fbank extraction) within the model's forward pass [cite: 11, 19]. 

**Extracting Embeddings for Individual Segments:**
Iterating over the VAD timestamps, we slice the original audio tensor and pass it to the encoder.

```python
import torch
import torchaudio

# Load the full audio file into memory
signal, fs = torchaudio.load("standardized_audio.wav") # shape: (1, total_samples)

embeddings = []
for seg in speech_timestamps:
    start_sample = int(seg['start'] * fs)
    end_sample = int(seg['end'] * fs)
    
    # Crop the audio chunk
    chunk = signal[:, start_sample:end_sample] # shape: (1, chunk_time)
    
    # If the chunk is too short (<0.5s), it may yield poor embeddings. 
    # ECAPA-TDNN works best with >1 second of audio.
    with torch.no_grad(): # Crucial for memory management
        # Encode the batch
        emb = classifier.encode_batch(chunk) 
        # emb shape: (1, 1, 192) for ECAPA-TDNN
        
        # Flatten to 1D numpy array for clustering
        embeddings.append(emb.squeeze().cpu().numpy())
```

---

## 4. Clustering Speaker Embeddings

Once we have a sequence of 192-dimensional ECAPA-TDNN embeddings, we group them into speaker identities using Hierarchical Agglomerative Clustering (HAC).

### 4.1 Distance Metric: Cosine vs. Euclidean
Speaker embeddings are trained using Additive Margin Softmax Loss to optimize angular distance [cite: 4, 5, 18]. Therefore, **cosine distance** is the strictly correct metric to use. Euclidean distance fails to account for the angular distribution of the hypersphere manifold on which these embeddings reside. 

Cosine distance is mathematically defined as:
\[ D_C(u, v) = 1 - \frac{u \cdot v}{\|u\|_2 \|v\|_2} \]

### 4.2 Agglomerative Clustering with SciPy
Using `scipy.cluster.hierarchy`, we generate a linkage matrix. For cosine distance, `average` or `complete` linkage often outperforms `Ward`'s method (which expects Euclidean distance).

```python
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster

# Convert list of embeddings to an (N, 192) numpy matrix
X = np.array(embeddings)

# 1. Generate the linkage matrix using cosine distance
Z = linkage(X, method='average', metric='cosine')
```

### 4.3 Determining the Optimal Number of Speakers
If the number of speakers is unknown, dynamic thresholding of the dendrogram is used. A common heuristic for ECAPA-TDNN embeddings is to cut the dendrogram at a distance threshold between $0.15$ and $0.30$. 

```python
# 2. Cut the dendrogram dynamically based on a distance threshold
clustering_threshold = 0.25 # Hyperparameter: tune based on dataset
speaker_labels = fcluster(Z, t=clustering_threshold, criterion='distance')

# speaker_labels is an array of integers starting from 1 (e.g., [1, 1, 2, 1, 3...])
```

---

## 5. Automatic Speech Recognition using OpenAI Whisper

With the audio diarized into segments and assigned to speakers, we transcribe the audio using OpenAI Whisper `20231117`.

### 5.1 API and Parameters
The exact API for inference is straightforward. On CPU, loading `large-v3` requires significant RAM (~10GB) and computational time [cite: 20, 21]. 

```python
import whisper

# Load model (Warning: large-v3 on CPU is extremely slow. Consider 'small' or 'base' for faster prototyping)
model = whisper.load_model('large-v3', device='cpu')
```

The transcription method is `model.transcribe()`. To extract word-level timestamps, `word_timestamps=True` must be passed [cite: 6, 22].
```python
result = model.transcribe(
    audio="standardized_audio.wav",
    language="en",          # Explicit language prevents auto-detect overhead
    word_timestamps=True,   # Required for precise alignment [cite: 6]
    verbose=False           # Suppresses console spam
)
```

### 5.2 Transcribing Numpy Arrays Directly
Whisper supports direct transcription of numpy arrays, avoiding disk I/O. The array must be a 1D `float32` numpy array sampled at 16 kHz [cite: 23].
```python
# Convert torchaudio tensor to 1D float32 numpy array
audio_np = signal.squeeze().numpy().astype(np.float32)

# Normalize if required, though Whisper handles typical PCM float32 ranges
result = model.transcribe(audio=audio_np, word_timestamps=True)
```

### 5.3 Result Dictionary Structure
The `result` object is a dictionary containing the full `text`, the detected `language`, and a list of `segments` [cite: 22]. 

Each segment in `result['segments']` is a dictionary with the following key structure:
*   `start` (float): Segment start time in seconds.
*   `end` (float): Segment end time in seconds.
*   `text` (str): The transcribed text for this segment.
*   `words` (list): Only present if `word_timestamps=True` [cite: 6]. A list of dictionaries for each word:
    *   `word` (str): The word text.
    *   `start` (float): Word start time.
    *   `end` (float): Word end time.
    *   `probability` (float): Confidence score.

---

## 6. Aligning Whisper Transcriptions with Diarization Labels

Whisper's VAD and segmentation logic operates independently of our Silero/SpeechBrain diarization timeline. Whisper segments often cross over true speaker boundaries. To map Whisper's text to the correct speaker, we perform **overlap-based assignment** at the word level.

### 6.1 Strategy: Intersection over Union (IoU) Mapping
For each word in `result['segments'][i]['words']`, we find which diarization segment overlaps with it the most.

```python
def assign_speaker_to_word(word_start, word_end, diarization_segments):
    """
    diarization_segments: list of dicts {'start': float, 'end': float, 'speaker': str}
    """
    max_overlap = 0
    assigned_speaker = "UNKNOWN"
    
    for seg in diarization_segments:
        # Calculate overlap duration
        overlap_start = max(word_start, seg['start'])
        overlap_end = min(word_end, seg['end'])
        overlap = max(0, overlap_end - overlap_start)
        
        if overlap > max_overlap:
            max_overlap = overlap
            assigned_speaker = seg['speaker']
            
    return assigned_speaker
```
By mapping each word to a speaker, we can group contiguous words assigned to the same speaker into a single, cohesive transcript line.

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

### 7.2 Writing RTTM using `pyannote.core.Annotation`
`pyannote.core` version 5.0.0 is built explicitly to manage this data format [cite: 9, 25]. It features a built-in RTTM writer via the `Annotation` object [cite: 9, 25].

```python
from pyannote.core import Annotation, Segment

# 1. Initialize the annotation object with a specific URI (file_id)
annotation = Annotation(uri="standardized_audio")

# 2. Populate the annotation with our clustered VAD segments
# Assuming speech_timestamps holds 'start'/'end' and speaker_labels holds integers 1, 2, 3...
for seg, label_idx in zip(speech_timestamps, speaker_labels):
    # Format speaker label like spk00, spk01
    speaker_label = f"spk{label_idx - 1:02d}" 
    
    # Pyannote tracks are assigned by assigning a Segment as the key
    # annotation[Segment(start, end)] = speaker_label
    annotation[Segment(seg['start'], seg['end'])] = speaker_label

# 3. Write directly to RTTM [cite: 9, 25]
with open("output.rttm", "w") as f:
    annotation.write_rttm(f)
```
*Gotcha Note:* `pyannote.core.Segment` objects are strictly immutable tuples [cite: 9]. If you need to shift a segment, you must instantiate a new `Segment`. Furthermore, assigning a segment to the `Annotation` dictionary automatically handles timeline resolution.

---

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

## 9. Common Pitfalls and Library Constraints

### 9.1 SpeechBrain 1.0.3 Deprecation Warnings
A major breaking change in the PyTorch ecosystem affects SpeechBrain v1.0.3: `torchaudio.list_audio_backends()` was deprecated in 2.8 and entirely removed in `torchaudio` 2.9 [cite: 17, 28]. Since SpeechBrain v1.0.3 invokes this function during import, executing the pipeline on environments with `torchaudio>=2.9` causes a fatal `AttributeError` [cite: 17, 28]. Because this pipeline specifies `torch==2.2.0` (and consequently `torchaudio==2.2.0`), this crash is circumvented. However, maintain strict virtual environment pinning.

### 9.2 Silero VAD 6.2.0 Breaking Changes
The migration to v6.x introduced a completely new package namespace (`silero_vad`). Legacy tutorials instructing the use of `torch.hub.load('snakers4/silero-vad', ...)` will still pull an older model but lack the improved stability and PyPI modularity of 6.2.0. The `get_speech_timestamps` output default also changed over the years; explicitly setting `return_seconds=True` ensures compatibility with `pyannote.core.Segment` (which relies on seconds) [cite: 1, 29]. Furthermore, the ONNX opset 16 implementation has mismatched tensor ranks in its branches, making the non-ONNX (PyTorch JIT) model the preferred target for generic CPU execution [cite: 30].

### 9.3 Whisper `large-v3` on CPU Memory Management
Running `openai-whisper`'s `large-v3` model on a standard CPU exposes significant operational bottlenecks. The model parameters alone consume ~3.1 GB of RAM, but the inference graph allocations easily push peak memory utilization beyond 10-12 GB [cite: 20, 21, 31]. 
*   **Mitigation:** Do not attempt to process the entire audio file via `model.transcribe()` in one continuous sweep if RAM is constrained. Instead, transcribe audio chunk by chunk (leveraging the VAD boundaries). However, be aware that chunking prevents Whisper from using previous context, which can mildly degrade transcription coherence. 

### 9.4 Pyannote.core Immutability Gotchas
Objects like `pyannote.core.Segment` and `pyannote.core.Timeline` have strict immutability rules. A `Segment` cannot have its `start` or `end` attributes altered post-instantiation [cite: 9]. You must instantiate a new `Segment`. While the `Annotation` object behaves like a dictionary, overlapping segments assigned to the exact same track will override each other, so ensure uniqueness or use multi-track allocation if mapping overlapping speech.

---

## 10. Complete Working Code Example

The following script integrates all discussed modules into a cohesive, functional pipeline executing on Python 3.11 with the exact specified library versions.

```python
import os
import subprocess
import torch
import torchaudio
import numpy as np
import whisper
from scipy.cluster.hierarchy import linkage, fcluster
from pyannote.core import Annotation, Segment

# 1. Silero VAD 6.2.0
from silero_vad import load_silero_vad, get_speech_timestamps

# 2. SpeechBrain 1.0.3
from speechbrain.inference.speaker import EncoderClassifier

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
INPUT_MP4 = "meeting.mp4"
WAV_FILE = "standardized.wav"
URI = "meeting_recording"
CLUSTERING_THRESHOLD = 0.25

# ---------------------------------------------------------
# Step 1: FFmpeg Extraction
# ---------------------------------------------------------
def extract_audio(input_file, output_file):
    print("Extracting audio via FFmpeg...")
    cmd = [
        "ffmpeg", "-y", "-i", input_file, 
        "-vn", "-acodec", "pcm_s16le", 
        "-ar", "16000", "-ac", "1", output_file
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# ---------------------------------------------------------
# Step 2: VAD using Silero 6.2.0
# ---------------------------------------------------------
def run_vad(audio_path):
    print("Running Silero VAD...")
    model = load_silero_vad(onnx=False)
    wav_tensor, fs = torchaudio.load(audio_path) # returns (1, time)
    
    # get_speech_timestamps expects a 1D tensor
    speech_timestamps = get_speech_timestamps(
        wav_tensor.squeeze(), 
        model, 
        sampling_rate=16000, 
        return_seconds=True,
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=100
    )
    return wav_tensor, fs, speech_timestamps

# ---------------------------------------------------------
# Step 3 & 4: SpeechBrain Embedding & Clustering
# ---------------------------------------------------------
def diarize_segments(wav_tensor, fs, speech_timestamps):
    print("Extracting ECAPA-TDNN embeddings...")
    classifier = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb', 
        savedir='/tmp/speechbrain_encoder',
        run_opts={"device": "cpu"}
    )
    
    embeddings = []
    valid_timestamps = []
    
    for seg in speech_timestamps:
        start_samp = int(seg['start'] * fs)
        end_samp = int(seg['end'] * fs)
        chunk = wav_tensor[:, start_samp:end_samp]
        
        with torch.no_grad():
            emb = classifier.encode_batch(chunk)
            embeddings.append(emb.squeeze().numpy())
            valid_timestamps.append(seg)
            
    print("Clustering embeddings...")
    X = np.array(embeddings)
    Z = linkage(X, method='average', metric='cosine')
    labels = fcluster(Z, t=CLUSTERING_THRESHOLD, criterion='distance')
    
    # Map back to segments
    diarization_data = []
    for seg, label in zip(valid_timestamps, labels):
        diarization_data.append({
            'start': seg['start'],
            'end': seg['end'],
            'speaker': f"spk{label-1:02d}"
        })
    return diarization_data

# ---------------------------------------------------------
# Step 5: Export to RTTM via pyannote.core 5.0.0
# ---------------------------------------------------------
def export_rttm(diarization_data, output_file):
    print(f"Exporting RTTM to {output_file}...")
    annotation = Annotation(uri=URI)
    for seg in diarization_data:
        annotation[Segment(seg['start'], seg['end'])] = seg['speaker']
        
    with open(output_file, "w") as f:
        annotation.write_rttm(f)

# ---------------------------------------------------------
# Step 6: Whisper Transcription & Alignment
# ---------------------------------------------------------
def transcribe_and_align(audio_path, diarization_data):
    print("Loading Whisper large-v3 (CPU)...")
    model = whisper.load_model("large-v3", device="cpu")
    
    print("Transcribing with word-level timestamps...")
    result = model.transcribe(audio_path, language="en", word_timestamps=True, verbose=False)
    
    aligned_transcript = []
    for segment in result['segments']:
        if 'words' not in segment:
            continue
            
        for word in segment['words']:
            w_start, w_end = word['start'], word['end']
            w_text = word['word'].strip()
            
            # IoU Mapping
            max_overlap = 0
            assigned_speaker = "UNKNOWN"
            for d_seg in diarization_data:
                o_start = max(w_start, d_seg['start'])
                o_end = min(w_end, d_seg['end'])
                overlap = max(0, o_end - o_start)
                if overlap > max_overlap:
                    max_overlap = overlap
                    assigned_speaker = d_seg['speaker']
                    
            aligned_transcript.append({
                'start': w_start,
                'end': w_end,
                'speaker': assigned_speaker,
                'text': w_text
            })
    return aligned_transcript

# ---------------------------------------------------------
# Step 7: Export to ASS Subtitles
# ---------------------------------------------------------
def format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int(round((seconds - int(seconds)) * 100))
    if centisecs == 100:
        centisecs = 0
        secs += 1
        if secs == 60:
            secs = 0
            minutes += 1
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

def export_ass(aligned_transcript, output_file):
    print(f"Exporting ASS to {output_file}...")
    
    # Group words by speaker turn for cleaner subtitles
    grouped_lines = []
    if not aligned_transcript: return
    
    current_speaker = aligned_transcript['speaker']
    current_start = aligned_transcript['start']
    current_end = aligned_transcript['end']
    current_text = [aligned_transcript['text']]
    
    for word in aligned_transcript[1:]:
        # Split on speaker change or silence > 1.5 seconds
        if word['speaker'] != current_speaker or (word['start'] - current_end > 1.5):
            grouped_lines.append({
                'start': current_start,
                'end': current_end,
                'speaker': current_speaker,
                'text': " ".join(current_text)
            })
            current_speaker = word['speaker']
            current_start = word['start']
            current_text = [word['text']]
        else:
            current_text.append(word['text'])
        current_end = word['end']
        
    # Append the final line
    grouped_lines.append({
        'start': current_start, 'end': current_end, 
        'speaker': current_speaker, 'text': " ".join(current_text)
    })
    
    # Write the ASS Header [cite: 8]
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ass_header)
        for line in grouped_lines:
            s_time = format_ass_time(line['start'])
            e_time = format_ass_time(line['end'])
            spk = line['speaker']
            txt = line['text']
            f.write(f"Dialogue: 0,{s_time},{e_time},Default,,0,0,0,,{{\\b1}}{spk}:{{\\b0}} {txt}\n")

# ---------------------------------------------------------
# Execution Main
# ---------------------------------------------------------
if __name__ == "__main__":
    extract_audio(INPUT_MP4, WAV_FILE)
    wav_tensor, fs, timestamps = run_vad(WAV_FILE)
    diarization = diarize_segments(wav_tensor, fs, timestamps)
    export_rttm(diarization, f"{URI}.rttm")
    aligned_words = transcribe_and_align(WAV_FILE, diarization)
    export_ass(aligned_words, f"{URI}.ass")
    print("Pipeline execution complete.")
```

**Sources:**
1. [stackademic.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGL_X2Lm-4N0WWJM4_0QW-7gmiWl41NKG_eIPruhOsAy5cyaCwEnNOnzjxhwpvdSGM3HCbEeX2rO8-CNQf_6Q009poHgCFLyDt8D6rkApklTB3IUDADVPAzqez2FZPJwdOhSZMFyTGMTuOGAkP0eLgqlZa9DkwtfzE6j_C5E2FV1OQMoauN0r43Ogpgih9uYyrHk0H3NRW25Rh7JAs2lE7Ivw==)
2. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFvAvffbm6HIn_ZjKtxqC_xwgf8-gcWha0jgdDSnKScQMlewOkbXbkKHp7mDNuAKBFoutIURIt3FQCEkC9gU1zodIDqcNAWMhTdeNUt9xJQPh4X9uNOue0bm48=)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGyH2RMCW0akdFJQ52YC3ysQhXKd9brjUKTwh9E80KlILU7nInrJ3wQ5nBiIv1vvQqqziP1Qa8gct0kFsdOctmzW0VdfzUVqGo8nqDwhrvM9whS1vs6G-5AFB2QJSGsxV8pwWd2NWC1)
4. [zenn.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEzJbIe87CXecpVjHbDmqWRzpiMBOt9YQ5CQPvO2iEfyepDSLAmiAsKzUCrCW2-5tVUzvMb-yfdOAv8mA3i7RIP1q8_NjDoN4hGlEO4QnvUc81K5Wa8VVI_gson9Cb-k0Le1fo=)
5. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEGkMUK-qLmZjpYhNcWCgztXakW2YejJf_Nu069GUHM7TmYxFkG_g8kbCnfCJreXym6-piruPeUFC0IA44qf5jarhHDj1knHOJeq_rZxj0nDeCJJMdEjdE4gKQCEZyn4QaZyb4-zDm5koxVfj1ROQ==)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE9ofW667xWijGgjEmndmde4CIo9qPDH6R5aNrDHGdpvWySWDcsvlkX3k-6PvtmqYKiDd3WQ9kZjD3knkgU_PNrX_pxx0CRAAoQtL94tYMmsSE6p0DVrEtNZxXEkOfrhkIvk2qsUwyelpexE0JhvFTb2Vx2FLTtEPraFWgnue4X7mLNi97UHL6K_5BMLrVaP8rHBn3YRRErNFzf1Sby)
7. [fandom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGNxAltaDFcwSKWM9Ux7fRb0On1aStbqMQwh6c7kC2-zmKRj62nw6pcdmUHQ4xeIw4E2ZDjVjV_qoeyR7ZvLg4CmrwitFx8pdrJwgPLuDz1AttzLU_Nx9vv6YrjfIWow0ZPqDIWT4587cOC)
8. [conversiontools.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQlY806Dh1q38BG-PyVCwC8rdkQmBxkb2ukKODAlTn_D0KkxQQQhYLXk9O2P2_F-twLhB21U3fg9dye6zsegMGNS-Zo5jz0xEL9UvK855guSHsV0673w3ULR_YiA1LYOMoDBM=)
9. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQELMrIiGOtPy5zSGCmGCeLQzQ5nBBBOp-0gNKTZJrEwdD5kMoKOgDp7I1QrZDbh0waFSwu8KbJ7cmocRt-MrzxvNJcP39H_Bf-kk7gKW5Bi-eah2cKFR3Gn8q0ferseQ1yr4OI9wDHztFxVfKw=)
10. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6mATyPHQ7yjsncKpaNYPmAH-BMCbN8lqplQQNp2EJsxTjIwWmcCOPtrg8y_SXYw6-ibAJUr1QEyDI9ccbfQxw8grz6gypvLmWsPLjWc220wYJ9faLh1GU2Kw9eeMnBabrMKXeskWma-qZoSD4)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGCMXejxYIhGsyJKsE6riZr1SM94re-nhwbYOfUvgOCw8ERUBvOBE5wsJ6aTzioEXWmA09osBlYmWGQYcskav-4kD3at4QaLuiG4N6nDFwDqFlRtPEcEMUHZxw5yoyCNo61Agj0w0gablu1EUXUep0kuG_-p5l0csgkrrPCilWyw_iFbpcJ_wlySg==)
12. [pytorch.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGE2dGk3VaIAwJC_S9r_zylvRHd3m71YzTdX1Nx6rbI6Sr4DvjaFI0esPZb0z-ngWuaQwbS4snAdyZkYsRkqawcGlc-D53hc3jAFzi3QecwglocyNGq-xAMmmsSzjzEZdlKiAlJ8V0=)
13. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHs3muRsXxhSLcspn2ngxWif5x0jQKFLz11UCZfaR3ZbT6md7i2x7WFoZ5KhFiklEEmgNiR8UlE3sCnroUJTN7MWrZoClEym3h5s4L25_btzHb0q5bscx1L66EK60dXTuW0DD5bm2NdsQjGaRA=)
14. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF18UklMJxF-97c9oQQDNUwQ1vUAtdw9HW0EkrOSc8PRGlNmpTb23iZz9BRnGpf9TvEzVCMGHP8pFguQStnz0H-tbleKJ_vs-Q-Iwtj42QCMjcB9y2Yk4w8i29-ZUlDET7jRYbkdFA5klyGjC8=)
15. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHSEJdXjZfMNr-qAzH8tbQusaJo_axZkAnegnIThHhkrwHXrHDAlnkyAbYyDigTsjphyjCudX-qm_wd3qSDg-ps2ptA95ATnVj-azEbg_AwwdLZcibVAjZhzjrcmDimgShDc1YjIRCQD7gUxJoL800dYaRBrmkLApHTxoYATHYzxWokUxOJl1MDhkD_L9R8EZwNgivrWj4ivime-b5vfYUiGAlBfEOz)
16. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE8sDRW-fqqtWDZMEH7hRx1xJdbYw_Vyx9oqM0179JFtt1TiBR4FeiBQYg0QCNInVrTX9W5_EMDxWt-kSxmkxVwsc_oB3HfDlxfRWSv0AeGJ_Zyhj0Z-x1T_Q4-m9H-7aDJaejtTC8VydiaBMB3ZuHe7gJhuE-tD4Dr1k19U3v6IvOP822S)
17. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGR7iCFPB7vntUCS2pBpR1VTBTHlKcV7MdjDjnTgPFzZzUZ891ZVNIfgByK9yceaisbeFi3jY-s9Z7c-lLGxltcnHnUlTHarzhzp59Kbv7B58a58k7rMalyKlbiONdHuQ3R6a28OAYKJ2GkQaM=)
18. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7-ujMOjQ0H7t_RNkHL0QOqoUtLXnZVr73A8BCh5W1lK_jDB5diwXBbE7ENcQZJ5q7RSNrMom8voC504DxKeo8O-w4oafXTS94gWL09o3h34gCTFH9mbTsTjHrR3uzprK2p5PQwh81gGyQWD1BmoQ=)
19. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGvxiIXVPFqxNEpgDZZtyWLkmBhXBwrWD8M47npWJR6o5wmT9Nzb0-gQIUEl9Xb9yJU4kj5gVwDzay3SvyYBnaxuWK5YJW7P9ZJqWI9aOnu_OOu39J03xi4JuHMC_RWq8uySrXs-GaPy8Kt6SMSdaAEN43cnVVAODrCC1zEpbDE8fhoKsj21X6zjDEH7fqR395DYI_fj-X4BK2fpfY2GZ64NVLB4BEjxdFMRMXvdsqwbofTjbGUvs4Mfuo1dc3Pp01pSg==)
20. [qiita.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHI_fJ2v10GbcZQ9loydwK4aHFBL3-iz1wRrhbhHg2TaXkw85Cwpcn5vvS8oppAUbD85cHbUI1FIUW5AxFfG1cGlbmsoVXA5ScTIe-QO7BaYINHoQ2StggY1R-lmJninh2EiB_cDyMHmVrrv60=)
21. [usegalaxy.eu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAKnt14M84YnFgc_GEtnFsVCZlm4ZCquXw9-KzSsEjWBkWIZLmfKmNyDT1yN0YhErrrh7xYvQA9_FhdX5B6tuZMB0BImYCa_tR0cziWTfUYyzposJynqopiUvw)
22. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGLMNEpZ5GYy7DnFpzn30LtqGblvJ4dBJkqZ2Wf5yDDtgiBDl3fNnesk9OEyetspRjD90zQ1nyU6VYx2Uv2MEX01sCq2Lt6beYiWsdHGqkGTS8lkGjrp4juhOXorhZFC6Wec70qOi1Jtw==)
23. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0GzlesF0xeRxdJBOPsGZQObhB6E3lSSY5UUEqdIsU6iYzNj6YWWrujR380kzrHnDccAiKnKRILcWUXVCY4mF-4loW6Spfo3Gio9Uj1I8cd7k_CKqCPwMI2wNvFq7tLGUQGr7EupJH9oJ5VTH6XaLQ2s2U_XeLrHqEXrv2YW_69u12yBdtYpb_B1mlG_Ne8aZH)
24. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEKprBh29ayIxi2-z8SlVYj6ruBuRBfvv2ahlE7BmjKCicjN6sjKcszj0KvdxSAaFhSyd_IGhX7Tjmw4oNjYfBdPwAxKmerVimE9rc1W0u5YhdJpETz0PV7VIYjwyYRowLB4EFAKGrr4dbNnOawNmUbaHzJCDbmOMIUI8EDePgr2NypxGjjIvyKy_JRT2xq-FUIvHI_R1PrsVPNima74YXBrimF0XzTpGZL-A==)
25. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4n96I13iwb6_TORS5d05l0tHrnoYPDBF2me5QrwtxVqGhncQYwspkZvqcuzlKHXR5O9fURlzoxltWZRqpxSalqBlBenkYzCjsMkVOPihXx0sejXe1xe_siKw87febTXf-OxRXeEK4P3ei1pkfW4sgqTed_qtl0QG-rcdcwkflOaWqZa3C)
26. [subtitlekit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGln2_RtDRhzPpj-nAzuQcOQvo76p00oTFR37oQXpuzjm5XiBeVFEFk7qzth7nJYgauKm77otIAnGyLRSsK3k6RKq9rrmkZJYdTNslpn_E5RThg-KMNFlP-hi_UDg==)
27. [customsforge.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPh8smdwkoWa94fzBunZb07tWDxczeMXIqhqyKfV0_7L3t1T6leWikETrL0w3xiDwEpYYO8VgQDMHoRVw-DCP9Pz6Yn9AnUAvtNLQ5Avlzu8Ffu8WhcrDehpclfN8R7L9locO4u9wXmEXZlOikhAA2oGITr8ACaSU3JV9GF2Lp_4Ux38Wmj2jk8uq6rAtZgU2Q532OVQV-9Eo=)
28. [huggingface.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEaJz8s9vtNm758I3GKdBJ6aR78kwhNNQW05Wg4TSuwO8-LQ58AO7kFj1HsT8pWLE-zSU3U4zVo7b5uJgqJRzGogCXejGrE7pXMJI1R_qWDqvOqmPQo__iI4zO3e7sm9sS7gZdJL0JClHDJX5OVTcI3e0W06AW5o_o998eZjkDZ93_-OtFEgPXYmOGryg==)
29. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG1-IpkOu5L_UFZUgWkP6XAx-B1AsUKyxiZi5ShCgRGZl4E0tMHN3Q-0WNYuKHOeyhwY7nFwJoZr1SvLw8pLzVBH04RTt9Z3rPWjb9PHcr7BvdPV13R9B3XkRk37w==)
30. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERrSrV4S99sr3euxDr_1-WDQ_whibUt_32URKj_ygKkY_UQHVxCmBvMGCL7y3ykaGuAEWeUioTfIhndc0fCTzG2k0AI_gL-L_Vkk61TbWV3we11FTkpumCOCbtGzLQw9Ss6-4l6wla)
31. [cnblogs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSkylArmhu8q1_t8tKEoSqA1D6mHB-QH1_7QwrLT4BGVkC3QkFO0pM-mKqOO2q6GuZUfore1UAnk7OG81-0z9uWlQRmhDMhpD482W1n2KBsQhnWmkhNbDq102Y-OdOvwvnSzKpew==)
