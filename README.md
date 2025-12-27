# KeepSafe - Project Documentation & Development Plan

## Project Overview

KeepSafe is a local-first data preservation tool that helps users retain their personal social media memories with full metadata intact. It processes an official data export provided by the platform (e.g., Snapchat) and restores timestamps, location data, and file organization that are often lost when media is downloaded manually.

### Primary Goal

Ensure users can permanently archive their memories without losing dates, context, or organization.

### Core Principles

    User-owned data only (no scraping, no account access)
    Fully offline processing
    Privacy-first and transparent
    Simple, repeatable workflow


## Phase 1: Research & Planning

### 1. Platform Data Export Analysis

We must fully understand the structure of the official data export ZIP 

Key questions:
    
    What directories exist in the ZIP file?
    Where are media files stored?
    Which JSON files contain the metadata?
    How are media files referenced inside JSON?

Metadata fields to identify:

    Creation timestamp (UTC/local)
    Media type (photo/video)
    Filename or media ID
    Location (GPS coordinates, if present)
    Captions or text overlays
    Duration (for videos)

Deliverable:

A documented map of the export structure and metadata schema

### 2. Technical Requirements

Supported File Types:
    Images: JPEG, PNG
    Videos: MP4, MOV (if present)

Metadata Standards:
    Photos: EXIF
    Videos: XMP / container metadata

Platform Support (v1):
    macOS
    Windows -> Linux support likely acheivable with minimal changes

### 3. User Exoerience Design Goals

Key UX decisions for v1:

    Interface type:
        CLI for MVP
        GUI considered in later phase

    Workflow
        Single ZIP input
        Automatic processing with minimal prompts

    Output
        Clearly labeled archive folder
        Human-readable structure
        SUmmary report at completion


## Phase 2: Core Features (MVP)

### 1. ZIP File Processing

Functionality
    Accept a single platform data export ZIP
    Validate ZIP integrity
    Extract files to a temporary workspace

Implementation
    Identify and parse relevant JSON metadata files
    Location associated media files

### 2. Metadata Restoration

Core logic:
    Match each media file to its metadata entry
    Restore:
        Creation date/time
        Location (if available)
    Embed metadata into the file itself

Actions:
    Write timestamps into EXIF/XMP fields
    Rename files using a consistent timestamp-based format:
        YYYY-MM-DD_HH-MM-SS_originalname.jpg

### 3. File Organization

Output structure

    KeepSafe_Archive/
    ├── 2019/
    │   ├── 01/
    │   ├── 02/
    ├── 2020/
    │   ├── 06/
    │   └── 12/

Additional Behavior:
    Detect duplicates
    Append suffixes if needed
    Preserve original filenames when possible

### 4. Simple Interface (MVP)

Minimal GUI
    Drag-and-drop ZIP
    "Process" button
    Status + completion message


## Phase 3: Enhanced Features 

Advanced Organization
    Sort by location
    Filter by date range
    Separate photos and videos
    Custom folder rules

Cloud-Ready Export
    Google Photos-compatible structure
    iCloud-friendly naming
    Optional CSV / JSON catalog of all files

Data Validation & Reporting 
    Verify all metadata entries were processed
    Detect missing or corrupted files
    Generate warnings for incomplete metadata

Batch Processing
    Handle multiple export ZIPs
    Merge archives across years
    Prevent duplication across runs


## Development Roadmap

### Phase 1: Prototype (CLI)
    Obtain sample data export
    Parse JSON metadata
    Match media -> timestamps
    Rename files

### Phase 2: Metadata Embedding
    Writing EXIF/XMP timestamps
    Restore GPS data
    Validate on multiple file types

### Phase 3: Polish & Packaging
    Error handling
    Logging
    User documentation
    GUI
    Package executable (PyInstaller)

### Phase 4: Distribution
    GitHub repo
    Clear README
    Demo video
    Share with relevant communities