# Domain Reference for evo-diarization-pipeline

**Responsibility**: Audio extraction, VAD, speaker embedding extraction, clustering, and producing diarization segment data (start, end, speaker label).

**Key functions to implement**: extract_audio_from_video, run_silero_vad, extract_speaker_embeddings, cluster_speakers, run_diarization_pipeline

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

### 2.2 SpeechBrain VAD (`vad-crdnn-libriparty` v1.0.3)

Alternatively, SpeechBrain provides a Convolutional Recurrent Deep Neural Network (CRDNN) trained on Libriparty [cite: 10, 15]. 

**Exact API for v1.0.3:**
```python
from speechbrain.inference.VAD import VAD
import torchaudio

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

### 4.3 Determining the Optimal Number of Speakers

If the number of speakers is unknown, dynamic thresholding of the dendrogram is used. A common heuristic for ECAPA-TDNN embeddings is to cut the dendrogram at a distance threshold between $0.15$ and $0.30$. 

```python

### 9.1 SpeechBrain 1.0.3 Deprecation Warnings

A major breaking change in the PyTorch ecosystem affects SpeechBrain v1.0.3: `torchaudio.list_audio_backends()` was deprecated in 2.8 and entirely removed in `torchaudio` 2.9 [cite: 17, 28]. Since SpeechBrain v1.0.3 invokes this function during import, executing the pipeline on environments with `torchaudio>=2.9` causes a fatal `AttributeError` [cite: 17, 28]. Because this pipeline specifies `torch==2.2.0` (and consequently `torchaudio==2.2.0`), this crash is circumvented. However, maintain strict virtual environment pinning.

### 9.2 Silero VAD 6.2.0 Breaking Changes

The migration to v6.x introduced a completely new package namespace (`silero_vad`). Legacy tutorials instructing the use of `torch.hub.load('snakers4/silero-vad', ...)` will still pull an older model but lack the improved stability and PyPI modularity of 6.2.0. The `get_speech_timestamps` output default also changed over the years; explicitly setting `return_seconds=True` ensures compatibility with `pyannote.core.Segment` (which relies on seconds) [cite: 1, 29]. Furthermore, the ONNX opset 16 implementation has mismatched tensor ranks in its branches, making the non-ONNX (PyTorch JIT) model the preferred target for generic CPU execution [cite: 30].