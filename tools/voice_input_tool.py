"""
Voice input tool for Hermes - Record and transcribe audio from microphone
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from tools.registry import registry

# Check if dependencies are available
def check_requirements() -> bool:
    """Check if voice input dependencies are available."""
    # Check for Whisper
    try:
        import whisper
    except ImportError:
        return False
    
    # Check for any audio recording capability
    # PyAudio
    try:
        import pyaudio
        return True
    except ImportError:
        pass
    
    # System tools
    system = os.uname().sysname
    if system == "Darwin":
        # macOS: check for sox or afrecord
        checks = ["sox", "afrecord"]
    elif system == "Linux":
        # Linux: check for arecord or sox
        checks = ["arecord", "sox"]
    else:
        checks = []
    
    for tool in checks:
        if subprocess.run(["which", tool], capture_output=True).returncode == 0:
            return True
    
    # Check for ffmpeg as last resort
    return subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0

def voice_to_text(duration: int = 10, model: str = "base", language: Optional[str] = None, task_id: Optional[str] = None) -> str:
    """
    Record audio from microphone and transcribe to text.
    
    Args:
        duration: Recording duration in seconds (default: 10)
        model: Whisper model size (tiny, base, small, medium, large, turbo)
        language: Optional language code (e.g., 'en', 'es', 'fr')
        task_id: Task ID for tracking
    
    Returns:
        JSON string with transcribed text or error
    """
    try:
        import whisper
    except ImportError:
        return json.dumps({"error": "Whisper not installed. Run: pip install openai-whisper"})
    
    # Try to use the voice_input.py script if available
    voice_script = Path.home() / ".hermes" / "voice_input.py"
    if voice_script.exists():
        cmd = ["python3", str(voice_script), "-d", str(duration), "-m", model, "--json"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
            if result.returncode == 0:
                return result.stdout
            else:
                # Try direct implementation below
                pass
        except Exception:
            pass
    
    # Direct implementation
    audio_file = None
    
    # Try PyAudio first
    try:
        import pyaudio
        import wave
        
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        p = pyaudio.PyAudio()
        
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK)
        
        frames = []
        for _ in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Save to temp file
        audio_file = tempfile.mktemp(suffix=".wav")
        wf = wave.open(audio_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
    except Exception as e:
        # Fallback to system audio recording
        system = os.uname().sysname
        audio_file = tempfile.mktemp(suffix=".wav")
        
        if system == "Darwin":
            # Try sox on macOS
            if subprocess.run(["which", "sox"], capture_output=True).returncode == 0:
                cmd = ["sox", "-d", "-c", "1", "-r", "16000", audio_file, "trim", "0", str(duration)]
            else:
                return json.dumps({"error": "No audio recording tool available. Install sox: brew install sox"})
        
        elif system == "Linux":
            # Try arecord on Linux
            if subprocess.run(["which", "arecord"], capture_output=True).returncode == 0:
                cmd = ["arecord", "-f", "cd", "-t", "wav", "-d", str(duration), audio_file]
            elif subprocess.run(["which", "sox"], capture_output=True).returncode == 0:
                cmd = ["sox", "-d", "-c", "1", "-r", "16000", audio_file, "trim", "0", str(duration)]
            else:
                return json.dumps({"error": "No audio recording tool available. Install sox or alsa-utils"})
        else:
            return json.dumps({"error": f"Unsupported platform: {system}"})
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=duration + 5)
            if result.returncode != 0:
                return json.dumps({"error": f"Recording failed: {result.stderr.decode()}"})
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "Recording timeout"})
        except Exception as e:
            return json.dumps({"error": f"Recording error: {str(e)}"})
    
    if audio_file is None or not Path(audio_file).exists():
        return json.dumps({"error": "Failed to record audio"})
    
    try:
        # Load Whisper model and transcribe
        whisper_model = whisper.load_model(model)
        
        # Transcribe with optional language
        transcribe_opts = {"language": language} if language else {}
        result = whisper_model.transcribe(audio_file, **transcribe_opts)
        
        # Clean up temp file
        Path(audio_file).unlink(missing_ok=True)
        
        return json.dumps({
            "text": result["text"].strip(),
            "language": result.get("language", "unknown"),
            "duration": duration,
            "model": model
        })
        
    except Exception as e:
        # Clean up on error
        if audio_file and Path(audio_file).exists():
            Path(audio_file).unlink(missing_ok=True)
        return json.dumps({"error": f"Transcription failed: {str(e)}"})

# Register the tool
registry.register(
    name="voice_to_text",
    toolset="media",
    schema={
        "name": "voice_to_text",
        "description": "Record audio from microphone and transcribe to text using Whisper. Requires whisper and audio recording capability (pyaudio, sox, or ffmpeg).",
        "parameters": {
            "type": "object",
            "properties": {
                "duration": {
                    "type": "integer",
                    "description": "Recording duration in seconds",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 60
                },
                "model": {
                    "type": "string",
                    "description": "Whisper model size: tiny (fastest), base, small, medium, large, turbo (best speed/quality)",
                    "enum": ["tiny", "base", "small", "medium", "large", "turbo"],
                    "default": "base"
                },
                "language": {
                    "type": "string",
                    "description": "Optional language code (e.g., 'en', 'es', 'fr'). Auto-detect if not specified.",
                    "pattern": "^[a-z]{2}$"
                }
            }
        }
    },
    handler=lambda args, **kw: voice_to_text(
        duration=args.get("duration", 10),
        model=args.get("model", "base"),
        language=args.get("language"),
        task_id=kw.get("task_id")
    ),
    check_fn=check_requirements,
    requires_commands=["python3"]
)