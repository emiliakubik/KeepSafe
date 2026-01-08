#!/usr/bin/env python3
"""Test the extract_and_composite_zip function to see FFmpeg errors."""

import sys
import subprocess
import zipfile
from pathlib import Path
import requests

# Download one of the ZIP files for testing
test_url = "https://app.snapchat.com/web/deeplink/snapcode?username=Emilia_kubik&type=SVG&bitmoji"  # We'll use a real URL from memories

# But actually, let's just recreate the temp directory from a file we know exists
# Find a video that was just downloaded
video_path = Path("/Users/emiliakubik/code/KeepSafe/Snapchat_Memories/2025/03/2025-03-29_00-27-26_000941.mp4")
print(f"Testing with: {video_path}")

# Look for the original in memory_history.json to get the download URL
import json
json_path = Path("/Users/emiliakubik/code/KeepSafe/mydata~1767371977692/json/memories_history.json")
with json_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

# Find the memory with this timestamp
target_name = "2025-03-29_00-27-26_000941"
for memory in data.get("Saved Media", []):
    date_str = memory.get("Date", "")
    # Parse and format to match our filename format
    # ... we need to find the matching entry

# Actually, let's just download a fresh ZIP and test it
# Let me look for a recent memory URL
print("\nLooking for video ZIP URLs...")
video_zips = []
for memory in data.get("Saved Media", []):
    url = memory.get("Download Link", "")
    media_type = memory.get("Media Type", "")
    if ".zip" in url.lower() and media_type == "VIDEO":
        video_zips.append(url)
        if len(video_zips) >= 3:
            break

if video_zips:
    print(f"Found {len(video_zips)} video ZIPs to test")
    test_url = video_zips[0]
    print(f"Testing with URL: {test_url[:100]}...")
    
    # Download it
    temp_zip = Path("/tmp/test_memory.zip")
    print("Downloading ZIP...")
    response = requests.get(test_url, timeout=30)
    temp_zip.write_bytes(response.content)
    print(f"Downloaded {temp_zip.stat().st_size} bytes")
    
    # Extract and check structure
    print("\nExtracting ZIP...")
    temp_dir = Path("/tmp/test_extract_dir")
    temp_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(temp_zip, 'r') as zf:
        zf.extractall(temp_dir)
    
    files = list(temp_dir.glob('*'))
    print(f"Extracted files: {[f.name for f in files]}")
    
    main_file = None
    overlay_file = None
    
    for f in files:
        if '-main.' in f.name:
            main_file = f
            print(f"Main file: {f.name} ({f.stat().st_size} bytes)")
        elif '-overlay.' in f.name:
            overlay_file = f
            print(f"Overlay file: {f.name} ({f.stat().st_size} bytes)")
    
    if main_file and overlay_file:
        print("\nTesting FFmpeg overlay...")
        output_path = Path("/tmp/test_output_with_overlay.mp4")
        
        cmd = [
            'ffmpeg',
            '-i', str(main_file),
            '-i', str(overlay_file),
            '-filter_complex', '[1:v]format=rgba,colorchannelmixer=aa=1[overlay];[0:v][overlay]overlay=0:0:format=auto',
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '18',
            '-y',
            str(output_path)
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, timeout=120, text=True)
        
        print(f"\nReturn code: {result.returncode}")
        if result.returncode == 0:
            print(f"SUCCESS! Output: {output_path} ({output_path.stat().st_size} bytes)")
        else:
            print(f"FAILED!")
            print(f"STDERR:\n{result.stderr}")
            print(f"STDOUT:\n{result.stdout}")
    else:
        print("Missing main or overlay file!")
else:
    print("No video ZIPs found in memories_history.json")
