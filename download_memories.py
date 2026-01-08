#!/usr/bin/env python3

"""Download Snapchat memories listed in the local export JSON."""

import json
import os
import re
import subprocess
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import piexif
import pyautogui
import requests
from PIL import Image
from tqdm import tqdm

# =========================
# CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent
MEMORIES_JSON = BASE_DIR / "mydata~1767729842453/json/memories_history.json"
OUTPUT_DIR = BASE_DIR / "Snapchat_Memories"
ORIGINAL_BACKUP_DIR = BASE_DIR / "Original_Memories"

MAX_RETRIES = 3
DELAY_BETWEEN_DOWNLOADS = 0.3  # seconds (prevents rate limiting)

# =========================
# KEEP AWAKE THREAD
# =========================

def keep_awake():
    """Move the mouse periodically to stop the machine sleeping."""
    while True:
        pyautogui.moveRel(1, 0)
        time.sleep(2)
        pyautogui.moveRel(-1, 0)
        time.sleep(30)


awake_thread = threading.Thread(target=keep_awake, daemon=True)
awake_thread.start()

# =========================
# LOAD MEMORIES
# =========================

def load_memories(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("Saved Media", "Saved media", "Memories", "memories"):
            if key in data and isinstance(data[key], list):
                return data[key]

    return []


def parse_datetime(value: str):
    """Parse timestamps like '2019-03-30 01:35:25 UTC'."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return None


def set_file_times(path: Path, dt: datetime) -> None:
    """Apply the original memory timestamp to the downloaded file."""
    if not dt:
        return
    try:
        ts = dt.timestamp()
        os.utime(path, (ts, ts))
    except Exception:
        pass


def parse_location(value: Optional[str]) -> Optional[Tuple[float, float]]:
    """Parse strings like 'Latitude, Longitude: 36.65516, -86.5645'."""
    if not value:
        return None
    match = re.search(r"([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*)", value)
    if not match:
        return None
    try:
        return float(match.group(1)), float(match.group(2))
    except Exception:
        return None


def _deg_to_dms_rational(deg: float):
    deg_abs = abs(deg)
    d = int(deg_abs)
    m_float = (deg_abs - d) * 60
    m = int(m_float)
    s = round((m_float - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def create_xmp_sidecar(path: Path, dt: Optional[datetime], location: Optional[Tuple[float, float]]) -> None:
    """Create XMP sidecar file for video location/datetime metadata."""
    if path.suffix.lower() not in {".mp4", ".mov"}:
        return

    if not dt and not location:
        return

    xmp_path = path.with_suffix(path.suffix + ".xmp")
    xmp_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xmp_lines.append('<x:xmpmeta xmlns:x="adobe:ns:meta/">')
    xmp_lines.append('  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">')
    xmp_lines.append('    <rdf:Description')
    xmp_lines.append('      xmlns:exif="http://ns.adobe.com/exif/1.0/"')
    xmp_lines.append('      xmlns:exifEX="http://cipa.jp/exif/1.0/"')
    xmp_lines.append('      xmlns:xmp="http://ns.adobe.com/xap/1.0/"')

    if dt:
        dt_str = dt.isoformat() + "Z"
        xmp_lines.append(f'      exif:DateTimeOriginal="{dt_str}"')
        xmp_lines.append(f'      xmp:CreateDate="{dt_str}"')

    xmp_lines[-1] += ">"

    if location:
        lat, lon = location
        xmp_lines.append("      <exifEX:GeoLocation>")
        xmp_lines.append(f'        <rdf:Description exif:GPSLatitude="{lat}" exif:GPSLongitude="{lon}" />')
        xmp_lines.append("      </exifEX:GeoLocation>")

    xmp_lines.append("    </rdf:Description>")
    xmp_lines.append("  </rdf:RDF>")
    xmp_lines.append("</x:xmpmeta>")

    try:
        xmp_path.write_text("\n".join(xmp_lines), encoding="utf-8")
    except Exception:
        pass


def embed_video_metadata(path: Path, dt: Optional[datetime], location: Optional[Tuple[float, float]]):
    """Embed GPS and datetime directly into MP4/MOV using exiftool."""
    if path.suffix.lower() not in {".mp4", ".mov"}:
        return

    if not dt and not location:
        return

    # Validate it's actually a video file
    try:
        size = path.stat().st_size
        if size < 1024:  # Too small to be a real video
            return
    except Exception:
        return

    # Backup original in case exiftool corrupts it
    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        path.rename(backup_path)
    except Exception:
        return

    try:
        cmd = ["exiftool", "-overwrite_original"]
        
        if dt:
            dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
            cmd.append(f"-CreateDate={dt_str}")
            cmd.append(f"-ModifyDate={dt_str}")
        
        if location:
            lat, lon = location
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"
            cmd.append(f"-GPSLatitude={abs(lat)}")
            cmd.append(f"-GPSLatitudeRef={lat_ref}")
            cmd.append(f"-GPSLongitude={abs(lon)}")
            cmd.append(f"-GPSLongitudeRef={lon_ref}")
        
        cmd.append(str(backup_path))
        result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
        
        if result.returncode == 0:
            backup_path.rename(path)  # Success
        else:
            backup_path.rename(path)  # Restore even on error
            
    except Exception:
        # Exiftool failed, restore original
        try:
            backup_path.rename(path)
        except Exception:
            pass


def extract_and_composite_zip(zip_path: Path) -> Optional[Path]:
    """Extract ZIP and composite overlay onto main image or video."""
    try:
        temp_dir = zip_path.parent / f"{zip_path.stem}_temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)
        
        # Find main image/video and overlay
        files = list(temp_dir.glob('*'))
        main_file = None
        overlay_file = None
        
        for f in files:
            if '-main.' in f.name:
                main_file = f
            elif '-overlay.' in f.name:
                overlay_file = f
        
        if not main_file:
            # No main file found, cleanup and return
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        # Check if main file is a video
        is_video = main_file.suffix.lower() in {'.mp4', '.mov'}
        
        # Extract main file first
        output_path = zip_path.with_suffix(main_file.suffix)
        import shutil
        shutil.copy2(main_file, output_path)
        
        # If there's an overlay, save it separately and then composite
        if overlay_file and is_video:
            overlay_output = zip_path.with_name(f"{zip_path.stem}_overlay.png")
            
            # Convert overlay to PNG if it's WebP
            try:
                img = Image.open(overlay_file)
                img.save(overlay_output, 'PNG')
            except Exception as e:
                print(f"Could not convert overlay: {e}")
                shutil.copy2(overlay_file, overlay_output)
            
            # Now composite using FFmpeg (use temp name to avoid overwriting input)
            composited_path = zip_path.with_name(f"{zip_path.stem}_composited.mp4")
            final_path = zip_path.with_suffix('.mp4')
            cmd = [
                'ffmpeg',
                '-i', str(output_path),     # Base video
                '-i', str(overlay_output),   # Overlay PNG
                '-filter_complex', '[1:v][0:v]scale2ref[ovr][base];[base][ovr]overlay=0:0',
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-crf', '18',
                '-preset', 'veryfast',
                '-y',
                str(composited_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120, text=True)
            
            if result.returncode == 0 and composited_path.exists():
                # Replace the original with composited version
                output_path.unlink()  # Delete base video
                overlay_output.unlink()  # Delete overlay PNG
                composited_path.rename(final_path)  # Rename composited to final name
                output_path = final_path
            else:
                # Keep the non-composited video and overlay for manual inspection
                if composited_path.exists():
                    composited_path.unlink()
        
        elif overlay_file and not is_video:
            # Image overlay using PIL
            try:
                base = Image.open(main_file).convert('RGBA')
                overlay = Image.open(overlay_file).convert('RGBA')
                
                # Resize overlay to match base if needed
                if overlay.size != base.size:
                    overlay = overlay.resize(base.size, Image.Resampling.LANCZOS)
                
                # Composite
                composited = Image.alpha_composite(base, overlay)
                
                # Save as JPEG (convert back to RGB)
                output_path = zip_path.with_suffix('.jpg')
                composited.convert('RGB').save(output_path, 'JPEG', quality=95)
            except Exception:
                pass
        
        # Cleanup temp directory and ZIP
        shutil.rmtree(temp_dir, ignore_errors=True)
        zip_path.unlink()
        
        return output_path
        
    except Exception:
        return None


def apply_exif_metadata(path: Path, dt: Optional[datetime], location: Optional[Tuple[float, float]]):
    """Write DateTimeOriginal and GPS EXIF into JPEGs."""
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        return

    # Validate it's actually a JPEG (check magic bytes)
    try:
        with path.open("rb") as f:
            magic = f.read(2)
            if magic != b'\xff\xd8':  # JPEG magic bytes
                return
    except Exception:
        return

    # Backup original in case EXIF writing corrupts it
    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        path.rename(backup_path)
    except Exception:
        return

    try:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
        try:
            exif_dict = piexif.load(str(backup_path))
        except Exception:
            pass

        if dt:
            dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_str
            exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str

        if location:
            lat, lon = location
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = "N" if lat >= 0 else "S"
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = _deg_to_dms_rational(lat)
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = "E" if lon >= 0 else "W"
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = _deg_to_dms_rational(lon)

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(backup_path))
        backup_path.rename(path)  # Success, replace original
        
    except Exception:
        # EXIF write failed, restore original
        try:
            backup_path.rename(path)
        except Exception:
            pass


memories = load_memories(MEMORIES_JSON)
print(f"Found {len(memories)} memories")

failed = []

# =========================
# DOWNLOAD LOOP
# =========================

for idx, memory in enumerate(tqdm(memories, desc="Downloading Snapchat memories")):
    try:
        url = memory.get("Media Download Url") or memory.get("Download Link")
        if not url:
            continue

        raw_date = memory.get("Date")
        dt = parse_datetime(raw_date) if raw_date else None
        if not dt:
            dt = datetime.utcnow()

        location = parse_location(memory.get("Location"))

        date_str = dt.strftime("%Y-%m-%d_%H-%M-%S")
        year = dt.strftime("%Y")
        month = dt.strftime("%m")

        media_type = (memory.get("Media Type") or "").lower()
        ext = ".mp4" if "video" in media_type else ".jpg"

        media_id = (
            memory.get("Media ID")
            or memory.get("Media Id")
            or memory.get("Media Identifier")
            or memory.get("mid")
            or str(idx).zfill(6)
        )

        folder = OUTPUT_DIR / year / month
        folder.mkdir(parents=True, exist_ok=True)

        filename = f"{date_str}_{media_id}{ext}"
        filepath = folder / filename

        # Check if file exists and is complete
        if filepath.exists():
            # Peek at Content-Length to detect incomplete downloads
            try:
                head_resp = requests.head(url, timeout=10)
                expected_size = int(head_resp.headers.get("content-length", 0))
                actual_size = filepath.stat().st_size
                if expected_size > 0 and actual_size == expected_size:
                    continue  # File is complete, skip it
                elif expected_size > 0 and actual_size < expected_size:
                    filepath.unlink()  # Delete incomplete file, re-download below
            except Exception:
                continue  # If we can't check, assume it's complete and skip

        for attempt in range(MAX_RETRIES):
            resp = requests.get(url, stream=True, timeout=30)
            if resp.status_code == 200:
                content_length = resp.headers.get("content-length")
                bytes_written = 0
                
                with filepath.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_written += len(chunk)
                
                # Validate file size matches Content-Length header
                if content_length and int(content_length) != bytes_written:
                    filepath.unlink()
                    time.sleep(2)
                    continue
                
                # Backup original before metadata changes
                backup_folder = ORIGINAL_BACKUP_DIR / year / month
                backup_folder.mkdir(parents=True, exist_ok=True)
                backup_path = backup_folder / filename
                try:
                    import shutil
                    shutil.copy2(filepath, backup_path)
                except Exception:
                    pass
                
                # Detect if file type doesn't match extension
                try:
                    with filepath.open("rb") as f:
                        magic = f.read(2)
                        # ZIP files have PK signature (0x504B)
                        if magic == b'PK' and (ext == ".jpg" or ext == ".mp4"):
                            # Rename to .zip
                            new_filepath = filepath.with_suffix('.zip')
                            filepath.rename(new_filepath)
                            filepath = new_filepath
                            filename = filepath.name
                            ext = ".zip"
                            # Update backup too
                            new_backup = backup_path.with_suffix('.zip')
                            backup_path.rename(new_backup)
                            
                            # Extract and composite overlay
                            composited = extract_and_composite_zip(filepath)
                            if composited:
                                filepath = composited
                                filename = filepath.name
                                ext = filepath.suffix
                                # Update backup
                                backup_path = backup_folder / filename
                                try:
                                    import shutil
                                    shutil.copy2(filepath, backup_path)
                                except Exception:
                                    pass
                except Exception:
                    pass
                
                set_file_times(filepath, dt)
                
                # Apply metadata based on file type
                if ext == ".jpg":
                    apply_exif_metadata(filepath, dt, location)
                # Skip video metadata embedding for now - can cause corruption
                # elif ext == ".mp4":
                #     embed_video_metadata(filepath, dt, location)
                
                break
            time.sleep(2)
        else:
            failed.append(f"{filename} (incomplete/failed))")

        time.sleep(DELAY_BETWEEN_DOWNLOADS)

    except Exception:
        failed.append(str(memory.get("Media ID", f"unknown_{idx}")))

# =========================
# SAVE FAILURES
# =========================

if failed:
    with (BASE_DIR / "failed_downloads.txt").open("w", encoding="utf-8") as f:
        for item in failed:
            f.write(item + "\n")

print("\n✅ DONE")
print(f"❌ Failed downloads: {len(failed)}")
print(f"📁 Saved to: {OUTPUT_DIR}")
