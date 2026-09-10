import os
import numpy as np
import pysrt
import soundfile as sf

KOKORO_SAMPLE_RATE = 24000

LANG_CODE_MAP = {
    'ja': 'j',
    'en': 'a',
    'zh': 'z',
    'ko': 'k',
    'fr': 'f',
    'es': 'e',
    'de': 'd',
    'it': 'i',
    'pt': 'p',
}

VOICE_MAP = {
    'j': 'jf_alpha',
    'a': 'af_heart',
    'z': 'zf_xiaobei',
    'k': 'kf_sarah',
}

def parse_srt_file(srt_path):
    """Parse an SRT file and return list of segment dicts."""
    try:
        subs = pysrt.open(srt_path, encoding='utf-8-sig')
    except UnicodeDecodeError:
        subs = pysrt.open(srt_path, encoding='iso-8859-1')
    
    segments = []
    for sub in subs:
        start_sec = sub.start.ordinal / 1000.0
        end_sec = sub.end.ordinal / 1000.0
        duration_sec = end_sec - start_sec
        text = sub.text_without_tags.replace('\n', ' ').strip()
        segments.append({
            'index': sub.index,
            'text': text,
            'start_sec': start_sec,
            'end_sec': end_sec,
            'duration_sec': duration_sec,
        })
    return segments

def read_target_language(path):
    """Read target language code from file."""
    with open(path, 'r') as f:
        return f.read().strip()

def synthesize_segment(text, lang_code, voice=None, speed=1.0):
    """Synthesize speech using Kokoro TTS. Returns (audio_array, sample_rate)."""
    from kokoro import KPipeline
    
    kokoro_lang = LANG_CODE_MAP.get(lang_code, lang_code)
    if voice is None:
        voice = VOICE_MAP.get(kokoro_lang, 'jf_alpha')
    
    pipeline = KPipeline(lang_code=kokoro_lang)
    generator = pipeline(text=text, voice=voice, speed=speed, split_pattern=r'\n+')
    
    all_audio = []
    for (graphemes, phonemes, audio) in generator:
        if audio is not None:
            all_audio.append(audio)
    
    if not all_audio:
        raise ValueError(f"TTS generated no audio for text: {text[:50]}")
    
    combined = np.concatenate(all_audio)
    return combined, KOKORO_SAMPLE_RATE

def fit_audio_to_window(text, lang_code, voice=None, target_duration=None):
    """Synthesize and adjust speed to fit target duration window.
    Returns (audio_array, sample_rate, actual_duration, speed_used, duration_control).
    """
    # First pass: generate at normal speed to measure natural duration
    audio, sr = synthesize_segment(text, lang_code, voice, speed=1.0)
    natural_duration = len(audio) / sr
    
    duration_control = 'rate_adjust'
    speed_used = 1.0
    
    if target_duration is not None and target_duration > 0:
        if abs(natural_duration - target_duration) > 0.05:
            # Calculate required speed
            required_speed = natural_duration / target_duration
            # Clamp to quality bounds
            clamped_speed = max(0.5, min(2.0, required_speed))
            speed_used = clamped_speed
            
            # Regenerate with adjusted speed
            audio, sr = synthesize_segment(text, lang_code, voice, speed=clamped_speed)
            actual_duration = len(audio) / sr
            
            # If still too short, pad with silence
            if actual_duration < target_duration:
                silence_samples = int((target_duration - actual_duration) * sr)
                silence = np.zeros(silence_samples, dtype=np.float32)
                audio = np.concatenate([audio, silence])
                duration_control = 'pad_silence'
            # If still too long, trim
            elif actual_duration > target_duration + 0.2:
                max_samples = int(target_duration * sr)
                audio = audio[:max_samples]
                duration_control = 'trim'
            else:
                duration_control = 'rate_adjust'
    
    actual_duration = len(audio) / sr
    return audio, sr, actual_duration, speed_used, duration_control

def generate_tts_segments(segments_srt, source_srt, target_srt, lang_code, output_dir):
    """Full pipeline: parse SRTs, synthesize TTS for each segment, save WAV files.
    Returns list of result dicts with timing and file info.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    segments = parse_srt_file(segments_srt)
    source_texts = parse_srt_file(source_srt)
    target_texts = parse_srt_file(target_srt)
    
    results = []
    for i, seg in enumerate(segments):
        # Get source and target text for this segment
        src_text = source_texts[i]['text'] if i < len(source_texts) else ''
        tgt_text = target_texts[i]['text'] if i < len(target_texts) else ''
        
        target_duration = seg['duration_sec']
        
        audio, sr, actual_duration, speed_used, duration_control = fit_audio_to_window(
            tgt_text, lang_code, voice=None, target_duration=target_duration
        )
        
        # Save WAV segment
        output_path = os.path.join(output_dir, f'seg_{i}.wav')
        sf.write(output_path, audio, sr, subtype='PCM_16')
        
        results.append({
            'segment_index': i,
            'window_start_sec': seg['start_sec'],
            'window_end_sec': seg['end_sec'],
            'window_duration_sec': seg['duration_sec'],
            'source_text': src_text,
            'target_text': tgt_text,
            'tts_duration_sec': actual_duration,
            'speed_used': speed_used,
            'duration_control': duration_control,
            'output_path': output_path,
            'sample_rate': sr,
        })
    
    return results
