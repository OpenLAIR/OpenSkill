import json
import os


def create_chapter(time, title):
    """Create a chapter dictionary with integer time and string title."""
    return {"time": int(round(time)), "title": title}


def create_video_index(title, duration, chapters):
    """Create the full video index structure with video_info and chapters."""
    return {
        "video_info": {
            "title": title,
            "duration_seconds": duration
        },
        "chapters": chapters
    }


def validate_chapters(chapters, duration):
    """
    Validate chapter list against structural requirements:
    - First chapter starts at 0
    - Timestamps are strictly monotonically increasing
    - All timestamps within [0, duration]
    
    Returns list of error strings (empty = valid).
    """
    errors = []
    if not chapters:
        errors.append("No chapters provided")
        return errors

    if chapters[0]["time"] != 0:
        errors.append(f"First chapter must start at 0, got {chapters[0]['time']}")

    for i in range(1, len(chapters)):
        if chapters[i]["time"] <= chapters[i - 1]["time"]:
            errors.append(
                f"Ch {i + 1} '{chapters[i]['title']}' time {chapters[i]['time']} "
                f"<= ch {i} '{chapters[i - 1]['title']}' time {chapters[i - 1]['time']}"
            )

    for ch in chapters:
        if ch["time"] < 0 or ch["time"] > duration:
            errors.append(f"Time {ch['time']} for '{ch['title']}' out of range [0, {duration}]")

    return errors


def write_index(index, path):
    """Write the video index to a JSON file with pretty formatting."""
    # Ensure parent directory exists
    parent_dir = os.path.dirname(path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    with open(path, 'w') as f:
        json.dump(index, f, indent=2)
    print(f"Written index to {path}")


def load_transcript(path):
    """Load a saved transcript JSON file."""
    with open(path) as f:
        return json.load(f)