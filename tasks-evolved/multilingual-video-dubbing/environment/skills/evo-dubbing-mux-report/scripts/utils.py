import subprocess
import json
import os

def get_video_duration(filepath):
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0', filepath
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

def get_audio_duration(filepath):
    """Get audio file duration in seconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0', filepath
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

def calculate_drift(placed_start_sec, tts_duration_sec, window_end_sec):
    """Calculate drift: how far TTS end overshoots the window end."""
    placed_end = placed_start_sec + tts_duration_sec
    drift = placed_end - window_end_sec
    return round(drift, 3)

def mux_dubbed_video(video_path, segment_audio_paths, segment_starts_ms, output_path):
    """Mux TTS audio segments into video at precise timestamps.
    For single segment starting at 0, simply replace audio track.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    if len(segment_audio_paths) == 1 and segment_starts_ms[0] == 0:
        # Simple case: single segment at start, just replace audio
        cmd = (
            f'ffmpeg -y -i "{video_path}" -i "{segment_audio_paths[0]}" '
            f'-map 0:v -map 1:a -c:v copy -c:a aac -ar 48000 -ac 1 '
            f'-shortest "{output_path}"'
        )
    else:
        # Complex case: multiple segments with delays
        inputs = [f'-i "{video_path}"']
        filter_parts = []
        
        for idx, (audio_path, start_ms) in enumerate(zip(segment_audio_paths, segment_starts_ms)):
            inputs.append(f'-i "{audio_path}"')
            delay_ms = int(start_ms)
            filter_parts.append(f'[{idx+1}:a]adelay=delays={delay_ms}:all=1[a{idx}]')
        
        amix_inputs = ''.join([f'[a{i}]' for i in range(len(segment_audio_paths))])
        filter_parts.append(f'{amix_inputs}amix=inputs={len(segment_audio_paths)}:duration=first:dropout_transition=2[aout]')
        
        input_str = ' '.join(inputs)
        filter_str = ';'.join(filter_parts)
        
        cmd = (
            f'ffmpeg -y {input_str} -filter_complex "{filter_str}" '
            f'-map 0:v -map "[aout]" -c:v copy -c:a aac -ar 48000 -ac 1 '
            f'"{output_path}"'
        )
    
    result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path

def generate_report_json(source_lang, target_lang, original_duration, new_duration,
                         measured_lufs, speech_segments, output_path):
    """Generate the JSON report file."""
    report = {
        'source_language': source_lang,
        'target_language': target_lang,
        'audio_sample_rate_hz': 48000,
        'audio_channels': 1,
        'original_duration_sec': round(original_duration, 2),
        'new_duration_sec': round(new_duration, 2),
        'measured_lufs': round(measured_lufs, 1),
        'speech_segments': speech_segments
    }
    
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return output_path
