#!/usr/bin/env python3
"""Test voice input capability"""

import sys
import os

# Add user site-packages to path
import site
site.addsitedir('/Users/openclaw/Library/Python/3.9/lib/python/site-packages')

print("Testing voice input components...\n")

# Test Whisper
try:
    import whisper
    print("✓ Whisper is installed")
except ImportError as e:
    print(f"✗ Whisper not found: {e}")

# Test PyAudio
try:
    import pyaudio
    print("✓ PyAudio is installed")
    p = pyaudio.PyAudio()
    print(f"  Found {p.get_device_count()} audio devices")
    p.terminate()
except ImportError as e:
    print(f"✗ PyAudio not found: {e}")
except Exception as e:
    print(f"✗ PyAudio error: {e}")

# Test voice_input script
voice_script = os.path.expanduser("~/.hermes/voice_input.py")
if os.path.exists(voice_script):
    print(f"✓ Voice input script exists at {voice_script}")
else:
    print(f"✗ Voice input script not found at {voice_script}")

# Test voice_mode tool
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tools.voice_mode import check_voice_requirements
    reqs = check_voice_requirements()
    if reqs["available"]:
        print("✓ Voice mode requirements met")
    else:
        print("✗ Voice mode requirements not met:")
        print(f"  {reqs['details']}")
except Exception as e:
    print(f"✗ Could not check voice mode: {e}")

print("\nVoice input setup complete!")
print("\nUsage:")
print("  1. In Hermes CLI: /voice on  (enables voice mode)")
print("  2. Direct test: python3 ~/.hermes/voice_input.py -d 5")
print("  3. The 'voice_to_text' tool is now available to the agent")