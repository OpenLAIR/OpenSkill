# Domain Reference for evo-dubbing-mux-report

**Responsibility**: Construct FFmpeg filter_complex commands with adelay to place audio segments at exact timestamps, mux with original video (copy video stream), enforce 48kHz mono AAC output, compute drift metrics, and write the structured JSON report.

**Key functions to implement**: build_ffmpeg_mux_command, mux_dubbed_video, calculate_drift, get_video_duration, generate_report_json

---

## 4. FFmpeg Command-Line Integration for Audio/Video Dubbing


FFmpeg is the defacto standard for multiplexing the newly generated audio segments back into the video container. Invoking FFmpeg from Python via the `subprocess` module requires precise syntax management, particularly when aligning multiple TTS files to exact milliseconds.

## 8. Precise Duration Measurement Modalities



## 9. JSON Reporting and Drift Calculation


A dubbing utility module must log operations, especially temporal discrepancies. Due to floating-point representation in Python, raw timestamp floats like `1.4000000000000001` pollute JSON outputs.
*   **Precision**: `round(value, 3)` ensures precision up to the millisecond, which is the limit of acoustic human perception for synchronization.
*   **Drift Calculation**: `drift_sec` measures how far the TTS segment overshoots the subtitle time window.
    `drift_sec = round((start_time + actual_tts_duration) - original_end_time, 3)`
    A positive drift indicates the audio bleeds into the subsequent scene.

```python
import json

def generate_report(segment_data: list, output_json: str):
    report = []
    for seg in segment_data:
        actual_end = seg['start'] + seg['duration']
        drift = actual_end - seg['expected_end']
        report.append({
            "segment_id": seg['id'],
            "target_duration": round(seg['expected_end'] - seg['start'], 3),
            "actual_duration": round(seg['duration'], 3),
            "drift_sec": round(drift, 3)
        })
        
    with open(output_json, 'w') as f:
        json.dump(report, f, indent=4)
```

## 10. Common Integration Pitfalls and Best Practices


A production pipeline typically fails not at the synthesis stage, but during integration. The following are the most pervasive pitfalls: