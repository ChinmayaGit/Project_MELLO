# Project Mello 🚀
**Local-First AI Operating Layer & Desktop Assistant**

Mello is a persistent local intelligence system designed to sit between you and your operating system. Unlike traditional chatbots, Mello focuses on persistent memory, desktop automation, and modular skill orchestration—all running 100% locally for maximum privacy and low latency.

---

## 🌟 Core Vision
Mello is not just a chat interface; it's a **contextual automation engine**. It remembers what you do, understands your file patterns, and learns your preferences to proactively help you manage your digital workspace.

---

## 🛠 Features (Phase 1–5 Complete)

### 🧠 Phase 1 & 2: Foundation & Skill Engine
*   **Intelligent Folder Watching:** Real-time monitoring of your filesystem (e.g., Downloads).
*   **AI Classification:** Uses local **qwen3.5:0.8b** to categorize new files (Documents, Images, etc.).
*   **Modular Skill Architecture:** A "superpower" system where Mello can use specific tools:
    *   `mkdir` / `move`: Manage your folder structure.
    *   `read_file`: Analyze text, CSVs, and code.
    *   `open_app`: Launch installed software.
    *   `screenshot`: Take snapshots to "see" your desktop state.

### 🔍 Phase 3: Context Intelligence
*   **Semantic Memory:** Integrated **ChromaDB** for vector-based search. Mello "remembers" events by meaning, not just keywords.
*   **Episodic Logging:** Every action and detection is logged in a searchable SQLite database.
*   **Memory Compression:** Automatic summarization of past events to keep the AI's context lean and fast.
*   **Preference Learning:** Mello detects your habits (e.g., "User prefers snake_case for invoices") and stores them permanently.

### ⚡ Phase 4 & 5: Automation & Advanced AI
*   **Desktop Control:** Open any Windows application or run PowerShell commands.
*   **Self-Healing Workflows:** If a command fails, Mello automatically analyzes the error and tries a different approach.
*   **Windows-Smart:** Built-in translation for Linux commands (`touch`, `ls`) to their Windows equivalents.

---

## 🖥 The Web Dashboard
Mello features a modern, dark-themed web interface (FastAPI + Vanilla CSS) accessible at `http://localhost:8000`.

*   **Intelligence Layer:** Real-time streaming chat with **Voice Input (Mic)**.
    ![Intelligence Layer](pics/Screenshot%20(6).png)
*   **App Explorer:** Browse and launch all installed Windows applications with one click.
    ![App Explorer](pics/Screenshot%20(7).png)
*   **Model Monitor:** View your local Ollama models with live status lights (Green = Active).
    ![Model Monitor](pics/Screenshot%20(8).png)
*   **Skill Manager:** Toggle specific "superpowers" ON/OFF and use the **Skill Builder** to create new ones.
    ![Skill Manager](pics/Screenshot%20(9).png)
*   **Reports & Logs:** View real-time episodic memory and file classification reports.
    ![Reports](pics/Screenshot%20(10).png)
    ![Logs](pics/Screenshot%20(11).png)
*   **Security Center:** Transparent view of Mello's "Sandbox" (Allowed folders and apps).
    ![Security Center](pics/Screenshot%20(12).png)

---

## 🚀 Quick Start

### 1. Prerequisites
*   [Ollama](https://ollama.com/) installed and running.
*   Models downloaded: `qwen3.5:0.8b` and `qwen3.5:4b`.
*   Python 3.10+ installed.

### 2. Setup
```powershell
# Clone the repository
# Install dependencies
pip install -r requirements.txt
```

### 3. Configure
Edit the `.env` file to set your watch path:
```text
WATCH_PATH=C:/Users/YourName/Downloads
THINK_ENABLED=true
```

### 4. Run
```powershell
python main.py
```
Open your browser to **`http://localhost:8000`** to start using Mello!

---

## 🔒 Security & Safety
Mello is built on the principle of **Deterministic AI**.
*   **Sandbox:** Mello can only access folders and apps explicitly listed in `security_policy.json`.
*   **Command Filter:** Dangerous shell keywords (like `rm` or `format`) are blocked by the Security Layer.
*   **Local Only:** No data ever leaves your machine. Your files and memories stay private.

---

## 📂 Project Structure
```text
mello/
├── main.py            # Entry point (Server + Watcher)
├── src/
│   ├── chat.py        # Streaming chat logic
│   ├── skills/        # Modular skill definitions
│   ├── memory.py      # SQLite & Vector DB management
│   ├── security.py    # Permission enforcement
│   └── server.py      # FastAPI REST API
├── static/            # Web Dashboard (HTML/CSS/JS)
└── .env               # Configuration
```

---
*Created with ❤️ as a local-first AI infrastructure.*
