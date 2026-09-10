# Domain Reference for evo-transcription-alignment

**Responsibility**: ASR transcription via Whisper, word-to-speaker alignment using temporal overlap, and grouping words into speaker-attributed transcript segments.

**Key functions to implement**: transcribe_audio, assign_speaker_to_word, align_transcript_with_diarization, group_words_into_lines

---

## 5. Automatic Speech Recognition using OpenAI Whisper


With the audio diarized into segments and assigned to speakers, we transcribe the audio using OpenAI Whisper `20231117`.

### 5.1 API and Parameters

The exact API for inference is straightforward. On CPU, loading `large-v3` requires significant RAM (~10GB) and computational time [cite: 20, 21]. 

```python
import whisper

### 5.2 Transcribing Numpy Arrays Directly

Whisper supports direct transcription of numpy arrays, avoiding disk I/O. The array must be a 1D `float32` numpy array sampled at 16 kHz [cite: 23].
```python

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