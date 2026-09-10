import subprocess
import json
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd

def resample_audio(audio, orig_sr, target_sr):
    """Resample audio array from orig_sr to target_sr using polyphase filtering."""
    if orig_sr == target_sr:
        return audio
    g = gcd(orig_sr, target_sr)
    up = target_sr // g
    down = orig_sr // g
    resampled = resample_poly(audio, up, down)
    return resampled.astype(np.float32)

def measure_lufs(audio_path):
    """Measure LUFS using FFmpeg loudnorm filter (pass 1). Returns stats dict."""
    cmd = (
        f'ffmpeg -hide_banner -i "{audio_path}" '
        f'-af loudnorm=print_format=json -f null -'
    )
    res = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    stderr_text = res.stderr.decode()
    
    # Extract JSON from stderr
    try:
        json_start = stderr_text.rfind('{')
        json_end = stderr_text.rfind('}') + 1
        json_str = stderr_text[json_start:json_end]
        stats = json.loads(json_str)
        return stats
    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Could not parse loudnorm JSON from FFmpeg: {e}\nStderr: {stderr_text}")

def get_lufs_value(audio_path):
    """Get the integrated LUFS value as a float."""
    stats = measure_lufs(audio_path)
    return float(stats.get('input_i', -23.0))

def normalize_loudness(audio_path, output_path, target_lufs=-23.0):
    """Two-pass ITU-R BS.1770-4 loudness normalization using FFmpeg loudnorm."""
    # Pass 1: Measure
    stats = measure_lufs(audio_path)
    
    # Pass 2: Normalize with linear mode
    cmd = (
        f'ffmpeg -y -i "{audio_path}" -af '
        f'"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:'
        f'measured_I={stats["input_i"]}:'
        f'measured_LRA={stats["input_lra"]}:'
        f'measured_TP={stats["input_tp"]}:'
        f'measured_thresh={stats["input_thresh"]}:'
        f'offset={stats["target_offset"]}:'
        f'linear=true" '
        f'-ar 48000 -ac 1 "{output_path}"'
    )
    result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path

def process_segment_audio(input_path, output_path, target_sr=48000, target_lufs=-23.0):
    """Full audio processing: resample + loudness normalize.
    Uses FFmpeg for both resampling and normalization in one pass.
    """
    # Read input
    audio, sr = sf.read(input_path, dtype='float32')
    
    # Resample if needed
    if sr != target_sr:
        audio = resample_audio(audio, sr, target_sr)
    
    # Save resampled intermediate
    temp_path = output_path + '.tmp.wav'
    sf.write(temp_path, audio, target_sr, subtype='PCM_16')
    
    # Normalize loudness
    normalize_loudness(temp_path, output_path, target_lufs)
    
    # Clean up temp
    import os
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    return output_path
