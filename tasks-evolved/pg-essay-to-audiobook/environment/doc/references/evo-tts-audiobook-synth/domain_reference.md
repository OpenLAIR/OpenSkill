# Domain Reference for evo-tts-audiobook-synth

**Responsibility**: TTS API integration (OpenAI, ElevenLabs, edge-tts, gTTS), retry/backoff logic, MP3 chunk generation, and audio concatenation into final output file

**Key functions to implement**: synthesize_with_openai, synthesize_with_elevenlabs, synthesize_with_local_tts, synthesize_text_to_audio, concatenate_audio_chunks

---

## 2. OpenAI TTS API Usage (2024-2025 Standards)


OpenAI's Text-to-Speech API offers high-fidelity, low-latency voice synthesis. Integrating it requires strict adherence to their SDK conventions and payload limitations [cite: 3, 4].

## 3. ElevenLabs TTS API Usage


ElevenLabs provides highly expressive, emotionally intelligent TTS models. Their Python SDK underwent a major paradigm shift moving from v0.x to v1.x [cite: 10, 11].

## 4. Audio Concatenation and MP3 Handling


Because TTS payloads must be chunked to respect API limits, the resulting output is a collection of fragmented MP3 files. Concatenating these segments into a single cohesive MP3 file presents specific audio engineering challenges.

## 6. Fallback to Local TTS (Ubuntu 24.04, No GPU)


Cloud APIs are subject to network timeouts, rate limiting (HTTP 429), and service outages. Implementing a local fallback ensures the utility operates deterministically. On an Ubuntu 24.04 headless environment without a GPU, massive open-source models (like local Whisper or TorToiSe) are unviable due to high inference latency on CPUs. 

The two optimal CPU-friendly, API-key-less alternatives are `gTTS` and `edge-tts` [cite: 20].

## 7. Common Operational Pitfalls

