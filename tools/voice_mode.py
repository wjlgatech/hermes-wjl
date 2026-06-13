"""
Voice mode for Hermes CLI - Real-time voice input and text-to-speech
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable

# Audio recording state
_audio_recorder = None
_recording_thread = None
_recording_active = False

def check_voice_requirements() -> Dict[str, Any]:
    """Check if voice mode requirements are met."""
    available = True
    missing_packages = []
    details = []
    
    # Check Whisper
    try:
        import whisper
    except ImportError:
        available = False
        missing_packages.append("openai-whisper")
        details.append("Whisper not installed (speech-to-text)")
    
    # Check for audio recording capability
    audio_available = False
    
    # Try PyAudio
    try:
        import pyaudio
        audio_available = True
        details.append("✓ PyAudio available")
    except ImportError:
        missing_packages.append("pyaudio")
    
    # Check system tools
    if not audio_available:
        system = os.uname().sysname
        if system == "Darwin":
            if subprocess.run(["which", "sox"], capture_output=True).returncode == 0:
                audio_available = True
                details.append("✓ SoX available (macOS audio recording)")
            else:
                details.append("Install SoX: brew install sox")
        elif system == "Linux":
            if subprocess.run(["which", "arecord"], capture_output=True).returncode == 0:
                audio_available = True
                details.append("✓ arecord available (ALSA audio recording)")
            elif subprocess.run(["which", "sox"], capture_output=True).returncode == 0:
                audio_available = True
                details.append("✓ SoX available (Linux audio recording)")
            else:
                details.append("Install audio tools: apt-get install alsa-utils sox")
    
    if not audio_available:
        available = False
        details.append("No audio recording capability")
    
    return {
        "available": available,
        "missing_packages": missing_packages,
        "details": "\n".join(details)
    }

def detect_audio_environment() -> Dict[str, Any]:
    """Detect if audio is available in the current environment."""
    warnings = []
    available = True
    
    # Check for SSH session (no local audio)
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        warnings.append("SSH session detected - no local microphone access")
        available = False
    
    # Check for Docker/container
    if Path("/.dockerenv").exists():
        warnings.append("Docker container - audio passthrough required")
        # Don't disable, as audio might be passed through
    
    # Check for WSL
    if "microsoft-standard" in os.uname().release.lower():
        warnings.append("WSL detected - limited audio support")
        # WSL2 might have audio with proper setup
    
    # Check for tmux/screen (shouldn't affect audio but good to know)
    if os.environ.get("TMUX"):
        warnings.append("tmux session - audio should work but check permissions")
    
    return {
        "available": available,
        "warnings": warnings
    }

class AudioRecorder:
    """Cross-platform audio recorder."""
    
    def __init__(self):
        self.recording = False
        self.audio_data = None
        self.thread = None
        self.temp_file = None
        
        # Detect recording method
        self.method = self._detect_method()
    
    def _detect_method(self) -> str:
        """Detect the best audio recording method."""
        # Try PyAudio first
        try:
            import pyaudio
            return "pyaudio"
        except ImportError:
            pass
        
        # Check system tools
        system = os.uname().sysname
        if system == "Darwin":
            if subprocess.run(["which", "sox"], capture_output=True).returncode == 0:
                return "sox"
        elif system == "Linux":
            if subprocess.run(["which", "arecord"], capture_output=True).returncode == 0:
                return "arecord"
            elif subprocess.run(["which", "sox"], capture_output=True).returncode == 0:
                return "sox"
        
        return "none"
    
    def start_recording(self) -> bool:
        """Start recording audio."""
        if self.recording or self.method == "none":
            return False
        
        self.recording = True
        self.temp_file = tempfile.mktemp(suffix=".wav")
        
        if self.method == "pyaudio":
            self.thread = threading.Thread(target=self._record_pyaudio)
        else:
            self.thread = threading.Thread(target=self._record_system)
        
        self.thread.start()
        return True
    
    def stop_recording(self) -> Optional[str]:
        """Stop recording and return the audio file path."""
        if not self.recording:
            return None
        
        self.recording = False
        if self.thread:
            self.thread.join(timeout=5)
        
        if self.temp_file and Path(self.temp_file).exists():
            return self.temp_file
        return None
    
    def cancel(self):
        """Cancel recording without returning audio."""
        self.recording = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.temp_file and Path(self.temp_file).exists():
            try:
                Path(self.temp_file).unlink()
            except:
                pass
    
    def _record_pyaudio(self):
        """Record using PyAudio."""
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
            while self.recording:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                except Exception:
                    break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Save to file
            if frames and self.temp_file:
                wf = wave.open(self.temp_file, 'wb')
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))
                wf.close()
                
        except Exception as e:
            print(f"PyAudio recording error: {e}", file=sys.stderr)
    
    def _record_system(self):
        """Record using system tools."""
        system = os.uname().sysname
        
        if system == "Darwin" and self.method == "sox":
            cmd = ["sox", "-d", "-c", "1", "-r", "16000", self.temp_file]
        elif system == "Linux" and self.method == "arecord":
            cmd = ["arecord", "-f", "cd", "-t", "wav", self.temp_file]
        elif self.method == "sox":
            cmd = ["sox", "-d", "-c", "1", "-r", "16000", self.temp_file]
        else:
            return
        
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while self.recording:
                if self.process.poll() is not None:
                    break
                time.sleep(0.1)
            
            if self.process.poll() is None:
                self.process.terminate()
                time.sleep(0.5)
                if self.process.poll() is None:
                    self.process.kill()
                    
        except Exception as e:
            print(f"System recording error: {e}", file=sys.stderr)

def transcribe_audio(audio_file: str, model: str = "base") -> Optional[str]:
    """Transcribe audio file to text."""
    try:
        import whisper
        model_instance = whisper.load_model(model)
        result = model_instance.transcribe(audio_file)
        return result["text"].strip()
    except Exception as e:
        print(f"Transcription error: {e}", file=sys.stderr)
        return None

def record_and_transcribe(duration: Optional[int] = None, model: str = "base") -> Optional[str]:
    """Record audio and transcribe to text.
    
    Args:
        duration: Recording duration in seconds (None for manual stop)
        model: Whisper model size
    
    Returns:
        Transcribed text or None on error
    """
    recorder = AudioRecorder()
    
    if recorder.method == "none":
        print("No audio recording method available", file=sys.stderr)
        return None
    
    print("Recording... Press Enter to stop" if duration is None else f"Recording for {duration} seconds...")
    
    if not recorder.start_recording():
        return None
    
    try:
        if duration:
            time.sleep(duration)
        else:
            input()  # Wait for Enter key
    except KeyboardInterrupt:
        recorder.cancel()
        return None
    
    audio_file = recorder.stop_recording()
    if not audio_file:
        return None
    
    print("Transcribing...")
    text = transcribe_audio(audio_file, model)
    
    # Clean up
    try:
        Path(audio_file).unlink()
    except:
        pass
    
    return text

# For compatibility with existing CLI code
def get_audio_recorder() -> AudioRecorder:
    """Get a singleton audio recorder instance."""
    global _audio_recorder
    if _audio_recorder is None:
        _audio_recorder = AudioRecorder()
    return _audio_recorder