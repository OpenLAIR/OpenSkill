import os
import io
import time
import subprocess
import asyncio


def synthesize_with_openai(text: str, output_path: str) -> bool:
    """Synthesize text using OpenAI TTS API. Returns True on success."""
    try:
        from openai import OpenAI
        client = OpenAI()  # Auto-reads OPENAI_API_KEY from env
        
        response = client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=text,
            response_format="mp3"
        )
        
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        # Verify file was written and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return True
        return False
    except Exception as e:
        print(f"OpenAI TTS failed: {e}")
        return False


def synthesize_with_elevenlabs(text: str, output_path: str) -> bool:
    """Synthesize text using ElevenLabs TTS API. Returns True on success."""
    try:
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            print("ElevenLabs API key not set")
            return False
        
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id="onwK4e9ZLuTAKqWW03F9",  # Daniel
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        
        with open(output_path, "wb") as f:
            for chunk in audio_generator:
                if chunk:
                    f.write(chunk)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return True
        return False
    except Exception as e:
        print(f"ElevenLabs TTS failed: {e}")
        return False


def synthesize_with_local_tts(text: str, output_path: str) -> bool:
    """Synthesize text using local TTS (edge-tts then gTTS). Returns True on success."""
    # Try edge-tts first
    try:
        import edge_tts
        
        async def _generate():
            communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
            await communicate.save(output_path)
        
        # Handle event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, _generate()).result()
            else:
                loop.run_until_complete(_generate())
        except RuntimeError:
            asyncio.run(_generate())
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            print("edge-tts succeeded")
            return True
    except Exception as e:
        print(f"edge-tts failed: {e}")
    
    # Try gTTS
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(output_path)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            print("gTTS succeeded")
            return True
    except Exception as e:
        print(f"gTTS failed: {e}")
    
    return False


def synthesize_text_to_audio(text: str, output_path: str) -> bool:
    """Try OpenAI -> ElevenLabs -> local TTS. Returns True on success."""
    # Try OpenAI first
    if synthesize_with_openai(text, output_path):
        return True
    
    time.sleep(1)
    
    # Try ElevenLabs
    if synthesize_with_elevenlabs(text, output_path):
        return True
    
    # Try local TTS
    if synthesize_with_local_tts(text, output_path):
        return True
    
    print(f"All TTS methods failed for chunk")
    return False


def concatenate_audio_chunks(chunk_files: list, output_file: str) -> bool:
    """Concatenate MP3 files into a single MP3 using pydub or ffmpeg."""
    # Try pydub first
    try:
        from pydub import AudioSegment
        
        combined = AudioSegment.empty()
        for f in chunk_files:
            if os.path.exists(f) and os.path.getsize(f) > 0:
                segment = AudioSegment.from_mp3(f)
                combined += segment
        
        combined.export(output_file, format="mp3", bitrate="128k")
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
            return True
    except Exception as e:
        print(f"pydub concatenation failed: {e}, trying ffmpeg")
    
    # Fallback to ffmpeg
    try:
        list_file = "/tmp/ffmpeg_list.txt"
        with open(list_file, "w") as f:
            for path in chunk_files:
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    f.write(f"file '{path}'\n")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_file
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(list_file):
            os.remove(list_file)
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
            return True
    except Exception as e:
        print(f"ffmpeg concatenation failed: {e}")
    
    return False
