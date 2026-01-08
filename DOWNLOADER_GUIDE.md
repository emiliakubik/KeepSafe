# Snapchat Memories Downloader

## Overview

`download_memories.py` is a Python script that automatically downloads all Snapchat memories from a local Snapchat data export (JSON file). It preserves original timestamps, GPS coordinates, and other metadata by embedding them into the downloaded files.

---

## What It Does

### 1. **Reads the Export JSON**
   - Loads `mydata~1767371977692/json/memories_history.json` (your Snapchat data export)
   - Extracts metadata for each memory: date, location, media type, and download URL
   - Supports both array format and nested "Saved Media" object structure

### 2. **Downloads Media Files**
   - Fetches each image/video from the download URL
   - Saves to organized folders: `Snapchat_Memories/YYYY/MM/`
   - Names files as: `YYYY-MM-DD_HH-MM-SS_<media-id>.jpg` (or `.mp4` for videos)
   - Retries up to 3 times if a download fails
   - Skips files that already exist locally

### 3. **Preserves File Timestamps**
   - Sets the downloaded file's modification and access time to the original memory's creation date
   - This ensures photos/videos show the correct date in your file explorer and media library

### 4. **Embeds EXIF Metadata** (JPEGs only)
   - **DateTimeOriginal**: The exact time the memory was saved
   - **DateTimeDigitized**: The capture/save time
   - **DateTime**: File creation timestamp
   - **GPS Coordinates**: Latitude and longitude from the Location field

### 5. **Keeps Your Machine Awake**
   - Runs a background daemon thread that moves the mouse every 30 seconds
   - Prevents your computer from sleeping during the download process

### 6. **Logs Failures**
   - Creates `failed_downloads.txt` with any files that couldn't be downloaded
   - Lists the media ID for easy reference

---

## How to Use

### Prerequisites
Ensure dependencies are installed:
```bash
.venv/bin/pip install requests tqdm pyautogui piexif
```

Or use requirements.txt:
```bash
.venv/bin/pip install -r requirements.txt
```

### Running the Script
From the repository root:
```bash
.venv/bin/python download_memories.py
```

The script will:
1. Load your memories JSON
2. Show a progress bar as it downloads each file
3. Print completion stats and the output directory

### Expected Output
```
Found 500 memories
Downloading Snapchat memories: 100%|████████| 500/500 [2:34:18<00:00, 18.65s/it]

✅ DONE
❌ Failed downloads: 2
📁 Saved to: /Users/emiliakubik/code/KeepSafe/Snapchat_Memories
```

---

## Configuration

Edit these constants in the script to customize behavior:

| Constant | Default | Purpose |
|----------|---------|---------|
| `BASE_DIR` | Script directory | Root for finding JSON and saving output |
| `MEMORIES_JSON` | `mydata~.../json/memories_history.json` | Path to your Snapchat export file |
| `OUTPUT_DIR` | `Snapchat_Memories` | Where to save downloaded files |
| `MAX_RETRIES` | 3 | Download retry attempts per file |
| `DELAY_BETWEEN_DOWNLOADS` | 0.3 seconds | Pause between downloads (prevents rate limiting) |

---

## File Structure

### Input
```
mydata~1767371977692/
├── json/
│   └── memories_history.json    # Your Snapchat memories metadata
└── html/
    └── memories_history.html    # (not used by script)
```

### Output
```
Snapchat_Memories/
├── 2019/
│   ├── 01/
│   │   ├── 2019-01-05_14-30-22_abc123.jpg
│   │   └── 2019-01-15_22-45-10_def456.mp4
│   └── 02/
│       └── 2019-02-01_09-12-30_ghi789.jpg
├── 2020/
│   └── ...
└── 2025/
    └── ...

failed_downloads.txt  # (if any downloads failed)
```

---

## Metadata Handling

### File Timestamps (All Files)
- **Modified Time**: Set to the memory's original creation date
- **Access Time**: Set to the memory's original creation date
- Allows photos to show correct date in Photos app, Finder, etc.

### JPEG EXIF Metadata
GPS coordinates are parsed from location strings like:
```
"Location": "Latitude, Longitude: 36.65516, -86.5645"
```

And stored as:
- **GPSLatitude**: 36° 39' 18.58" N
- **GPSLongitude**: 86° 39' 16.2" W

Allows photos to be geotagged in Apple Photos, Google Photos, and other apps.

### Videos
- File timestamps are set
- EXIF/metadata embedding is skipped (MP4s don't use EXIF)

---

## Error Handling

### Network Issues
- If a download fails, the script retries up to 3 times
- Failed downloads are logged to `failed_downloads.txt`
- Script continues to next file instead of crashing

### File Conflicts
- If a file already exists locally, it's skipped
- Allows resuming partial downloads without re-downloading

### Metadata Issues
- If EXIF writing fails, the file is still saved (with timestamps intact)
- If location parsing fails, GPS is simply not written
- Gracefully degrades rather than failing

---

## Key Features

✅ **Batch download** all memories at once  
✅ **Organized by date** (YYYY/MM folder structure)  
✅ **Preserve timestamps** (file mtime = memory creation time)  
✅ **Preserve location** (GPS EXIF tags for JPEGs)  
✅ **Resume-friendly** (skips existing files)  
✅ **Progress tracking** (tqdm progress bar)  
✅ **Sleep prevention** (keeps computer awake)  
✅ **Failure logging** (easy retry identification)  
✅ **Retry logic** (handles transient network errors)  

---

## Example Workflow

1. Download your Snapchat data from Snapchat's official export tool
2. Extract the ZIP to your workspace
3. Run the script: `.venv/bin/python download_memories.py`
4. Wait for downloads to complete (progress bar shows status)
5. Open `Snapchat_Memories/` folder in Finder/Explorer
6. Import photos into Apple Photos or Google Photos
7. Locations and dates will be preserved in your media library!

---

## Dependencies

- **requests**: HTTP library for downloading files
- **tqdm**: Progress bar display
- **pyautogui**: Mouse movement (prevents sleep)
- **piexif**: EXIF metadata writing for JPEGs

All are pinned in `requirements.txt` for reproducibility.

---

## Troubleshooting

### Downloads are slow
- Adjust `DELAY_BETWEEN_DOWNLOADS` (in seconds)
- Lower = faster but may hit rate limits
- Default 0.3s is safe for most connections

### Some files failed
- Check `failed_downloads.txt` for media IDs
- May be due to expired download links (7-day window from export)
- Try re-exporting from Snapchat if links are stale

### EXIF metadata not appearing
- Ensure files are JPEGs (.jpg/.jpeg)
- Some editing/conversion tools strip EXIF
- Check with `exiftool` or photo viewer's metadata display

### File timestamps not correct
- On macOS: Open in Photos app → Check "Info" panel
- On Windows: Right-click file → Properties → Details
- Some apps cache the old time; restart may help

---

## Notes

- The script is **resumable**: run it again to download any newly added memories
- Download links expire 7 days after Snapchat export; re-export if needed
- Computer must stay awake; daemon thread handles this automatically
- Safe for repeated runs (skips existing files)

