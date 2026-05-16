# Project Mello — Architecture & Roadmap

Save this as:

```text
MELLO_ARCHITECTURE.md
```

---

# Project Mello

## Vision

Mello is a:

* local-first AI operating layer
* workflow automation engine
* contextual memory system
* desktop intelligence assistant

Unlike normal AI assistants, Mello focuses on:

* persistent memory
* local execution
* workflow orchestration
* desktop understanding
* adaptive automation
* low-resource operation

Mello should eventually run on:

* Windows
* Linux
* Mac
* Android
* Edge devices

---

# Core Principles

## 1. Local First

Everything possible should run locally:

* LLMs
* memory
* workflows
* embeddings
* automation
* file indexing

Benefits:

* privacy
* offline support
* low latency
* no subscriptions
* full control

---

## 2. Deterministic AI

AI should:

* suggest
* classify
* generate plans

NOT directly execute dangerous operations.

Execution must always go through:

* validation
* structured workflows
* permission layers

---

## 3. Context-Aware Intelligence

Mello should NOT rely on raw chat history.

Instead:

* retrieve relevant memory
* compress information
* build dynamic context

---

# High-Level Architecture

```text
User
 ↓
Intent Detection
 ↓
Context Retrieval Engine
 ↓
Workflow Planner
 ↓
Execution Engine
 ↓
Memory Update System
```

---

# Core Components

# 1. Event System

The Event System detects:

* file creation
* downloads
* screenshots
* clipboard changes
* app launches
* browser activity
* USB devices
* scheduled tasks

Example:

```text
Downloads Folder
 ↓
New PDF Detected
 ↓
Trigger AI Classification
```

---

# 2. Context Engine (MOST IMPORTANT)

This is Mello’s real intelligence layer.

## Problem

Small local models lose context quickly.

## Solution

Hierarchical Context Memory System.

---

# Context Architecture

## A. Working Memory

Temporary active context.

Contains:

* current task
* active workflow
* recent files
* recent commands

Storage:

* RAM cache

TTL:

* minutes/hours

---

## B. Episodic Memory

Stores actions/events.

Example:

* moved invoice
* converted video
* cleaned desktop

Stored as:

* summarized events
* searchable logs

---

## C. Semantic Memory

Stores long-term user patterns.

Example:

```json
{
  "preferred_download_folder": "D:/Downloads",
  "movie_folder_structure": "Movies/Year/Movie Name",
  "naming_style": "snake_case"
}
```

---

## D. Workflow Graph Memory

Stores reusable workflow nodes.

Example:

```text
Download Movie
 ├── Detect Video
 ├── Extract Metadata
 ├── Download Thumbnail
 ├── Rename Folder
 ├── Generate Preview
 └── Organize Library
```

This becomes:

* reusable
* editable
* versioned

---

# Retrieval Engine

Before every AI request:

Mello:

1. detects intent
2. searches memory graph
3. retrieves ONLY relevant memories
4. compresses context
5. sends optimized prompt

This prevents:

* context overflow
* memory pollution
* token waste

---

# Recommended Memory Stack

| Purpose           | Tech               |
| ----------------- | ------------------ |
| Structured memory | SQLite             |
| Semantic search   | ChromaDB / LanceDB |
| Workflow graph    | NetworkX           |
| Cache             | In-memory          |
| Logs              | JSONL/Event store  |

---

# AI Model Architecture

## Small Model (Always Running)

Model:

* qwen3.5:0.8b

Tasks:

* classification
* intent detection
* quick parsing
* lightweight automation

---

## Main Reasoning Model

Model:

* qwen3.5:4b

Tasks:

* workflow planning
* complex reasoning
* automation generation
* debugging

---

## Optional Heavy Model

Model:

* qwen3.6

Tasks:

* advanced reasoning
* large planning tasks
* code generation

---

# Model Usage Strategy

| Task                 | Model |
| -------------------- | ----- |
| File classification  | 0.8B  |
| Folder organization  | 0.8B  |
| Intent parsing       | 0.8B  |
| Workflow generation  | 4B    |
| Long reasoning       | 3.6   |
| Memory summarization | 4B    |

---

# Skill System

Mello should NOT hardcode features.

Instead:

# Skills = Modular Workflow Units

Each skill contains:

* triggers
* actions
* context requirements
* permissions
* execution logic

---

# Example Skill Structure

```json
{
  "name": "movie_organizer",
  "trigger": "new_movie_detected",
  "steps": [
    "extract_metadata",
    "download_thumbnail",
    "rename_folder",
    "generate_preview",
    "move_to_library"
  ]
}
```

---

# Recommended Skill Engine

Instead of simple workflows:
use:

# Directed Workflow Graphs

Advantages:

* reusable nodes
* branching logic
* retries
* conditional execution
* easier debugging

---

# Example Workflow Graph

```text
Video Detected
 ├── Is Movie?
 │    ├── Yes → Fetch Metadata
 │    │            ├── Download Poster
 │    │            ├── Generate Thumbnail
 │    │            ├── Extract Preview Frames
 │    │            └── Organize Folder
 │    └── No → Archive
```

---

# Example Skills

# 1. Download Organizer

Capabilities:

* auto-sort downloads
* rename files
* detect duplicates
* categorize documents

Example:

```text
invoice_final_v2.pdf
 ↓
Amazon_Invoice_May_2026.pdf
```

---

# 2. Movie Organizer Skill

Features:

* detect movie folders
* fetch posters
* generate thumbnails
* create previews
* organize by genre/year

Folder Example:

```text
Movies/
 └── Interstellar (2014)/
      ├── poster.jpg
      ├── preview.mp4
      ├── metadata.json
      └── movie.mkv
```

---

# 3. FFmpeg Skill

Features:

* convert video formats
* compress videos
* extract frames
* generate previews
* create GIFs

Example Workflow:

```text
Input Video
 ↓
Extract Metadata
 ↓
Generate Thumbnail
 ↓
Compress
 ↓
Store Output
```

---

# 4. Screenshot Intelligence

Features:

* OCR screenshots
* categorize screenshots
* searchable screenshot history

---

# 5. Smart Desktop Cleaner

Features:

* group similar files
* archive old files
* remove duplicates
* organize clutter

---

# Execution Engine

The AI NEVER directly executes commands.

Instead:

```text
User Request
 ↓
AI Generates Structured Plan
 ↓
Validation Layer
 ↓
Execution Engine
 ↓
Permission Check
 ↓
Run Action
```

---

# Structured Action Example

```json
{
  "action": "move_file",
  "source": "Downloads/test.pdf",
  "destination": "Documents/PDFs/"
}
```

---

# Desktop Automation Layer

Capabilities:

* open applications
* keyboard/mouse automation
* clipboard management
* browser automation
* shell commands

Recommended Tools:

* Playwright
* PyAutoGUI
* AutoHotkey integration
* PowerShell
* FFmpeg

---

# Folder Intelligence System

Mello should understand:

* folder types
* content patterns
* user habits

Example:

* detect anime folders
* detect coding projects
* detect work documents
* detect media libraries

---

# Context Compression System

Raw events become summaries.

Example:

## Raw

```text
Moved 20 screenshots
Renamed 5 invoices
Organized 3 folders
```

## Summary

```text
User performed cleanup workflow.
```

## Higher Abstraction

```text
User prefers organized workspace.
```

---

# Suggested Tech Stack

| Layer                    | Tech     |
| ------------------------ | -------- |
| UI                       | Flutter  |
| Backend API              | FastAPI  |
| Automation               | Python   |
| High-performance workers | Rust     |
| Local AI                 | Ollama   |
| Memory DB                | SQLite   |
| Vector DB                | ChromaDB |
| Workflow Graph           | NetworkX |
| File Monitoring          | watchdog |
| Media Processing         | FFmpeg   |

---

# Initial Development Phases

# Phase 1 — Foundation

* folder watcher
* file classification
* move/rename files
* SQLite memory

---

# Phase 2 — Workflow Engine

* editable workflows
* graph execution
* rule system
* skill architecture

---

# Phase 3 — Context Intelligence

* retrieval engine
* memory compression
* semantic memory
* user preference learning

---

# Phase 4 — Desktop Automation

* app automation
* browser automation
* shell execution
* clipboard intelligence

---

# Phase 5 — Advanced AI

* adaptive workflows
* predictive automation
* self-healing workflows
* vision-based automation

---

# Long-Term Vision

Mello eventually becomes:

* AI desktop layer
* local automation OS
* contextual intelligence engine
* personal infrastructure assistant

The goal is NOT:

> “chatbot”

The goal is:

> “persistent local intelligence system”
