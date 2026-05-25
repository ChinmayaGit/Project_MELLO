from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import asyncio
import threading
import tempfile
import os
import ollama
import subprocess
from .memory import MemorySystem
from .chat import MelloChat
from .skills import SkillManager
from .compressor import MemoryCompressor

app = FastAPI()

# Global instances (will be initialized in main.py or startup)
memory       = None
mello_chat   = None
skill_manager = None
watch_path   = None
memory_enabled = True   # loaded from policy on init

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    async def event_generator():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def producer():
            try:
                for chunk in mello_chat.chat_stream(request.message):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, RuntimeError(str(e)))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=producer, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, RuntimeError):
                yield f"data: {json.dumps({'error': str(item)})}\n\n"
                break
            yield f"data: {json.dumps({'text': item})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/models")
async def get_models():
    try:
        # Get all local models
        models_info = ollama.list()
        # Get running models (ps)
        # Note: ollama-python doesn't have a direct 'ps' yet in some versions, 
        # but we can infer or use subprocess if needed.
        return {"models": models_info['models']}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/skills")
async def get_skills():
    skills_data = [
        {
            "name":     name,
            "enabled":  skill.enabled,
            "desc":     skill.description,
            "category": getattr(skill, "category", "other"),
        }
        for name, skill in skill_manager.skills.items()
    ]
    return {"skills": skills_data, "manifest": skill_manager.get_skill_manifest()}

class AppPermissionRequest(BaseModel):
    name: str
    allowed: bool

class SecurityFolderRequest(BaseModel):
    path: str

class SecurityKeywordRequest(BaseModel):
    keyword: str

@app.post("/api/security/apps/toggle")
async def toggle_app_permission(request: AppPermissionRequest):
    if request.allowed:
        skill_manager.security.allow_app(request.name)
    else:
        skill_manager.security.deny_app(request.name)
    return {"status": "success"}

@app.post("/api/security/folders/add")
async def add_folder(request: SecurityFolderRequest):
    skill_manager.security.add_folder(request.path)
    return {"status": "success"}

@app.post("/api/security/folders/remove")
async def remove_folder(request: SecurityFolderRequest):
    skill_manager.security.remove_folder(request.path)
    return {"status": "success"}

@app.post("/api/security/keywords/add")
async def add_keyword(request: SecurityKeywordRequest):
    skill_manager.security.add_keyword(request.keyword)
    return {"status": "success"}

@app.post("/api/security/keywords/remove")
async def remove_keyword(request: SecurityKeywordRequest):
    skill_manager.security.remove_keyword(request.keyword)
    return {"status": "success"}

class SkillToggleRequest(BaseModel):
    name: str
    enabled: bool

@app.post("/api/skills/toggle")
async def toggle_skill(request: SkillToggleRequest):
    success = skill_manager.toggle_skill(request.name, request.enabled)
    return {"status": "success" if success else "error"}

@app.get("/api/logs")
async def get_logs():
    logs = memory.query_episodic_memory(limit=50)
    # Format: (id, timestamp, type, description, metadata)
    formatted_logs = [
        {"id": l[0], "time": l[1], "type": l[2], "desc": l[3]} for l in logs
    ]
    return {"logs": formatted_logs}

# ── Memory API ────────────────────────────────────────────────────────────────

# Category → event_type mapping
MEMORY_CATEGORIES = {
    "files":  {"icon": "📁", "label": "File Memories",  "types": ["file_detected", "file_created", "file_moved"]},
    "skills": {"icon": "⚡", "label": "Skill Memories", "types": ["skill_execution", "skill_executed", "action_executed"]},
    "chat":   {"icon": "💬", "label": "Chat Memories",  "types": ["chat_message"]},
}

def _get_category(event_type):
    for cat, cfg in MEMORY_CATEGORIES.items():
        if event_type in cfg["types"]:
            return cat
    return "other"

class MemoryToggleRequest(BaseModel):
    enabled: bool

class CategoryToggleRequest(BaseModel):
    category: str
    enabled: bool

@app.get("/api/memory")
async def get_memory(search: str = "", limit: int = 500):
    entries = memory.search_episodic_memory(search, limit, 0)
    cats    = skill_manager.security.policy.get("memory_categories", {})

    # Build grouped tree
    groups = {k: {"icon": v["icon"], "label": v["label"],
                  "enabled": cats.get(k, True), "entries": []}
              for k, v in MEMORY_CATEGORIES.items()}
    groups["other"] = {"icon": "🗒", "label": "Other", "enabled": cats.get("other", True), "entries": []}

    for e in entries:
        cat = _get_category(e[2])
        groups[cat]["entries"].append(
            {"id": e[0], "timestamp": e[1], "type": e[2], "description": e[3]}
        )

    return {
        "enabled":    memory_enabled,
        "total":      memory.count_episodic_memory(),
        "groups":     groups,
    }

class MemoryAddRequest(BaseModel):
    description: str
    type: str = "chat_message"

@app.post("/api/memory/add")
async def add_memory_entry(request: MemoryAddRequest):
    mid = memory.add_episodic_memory(request.type, request.description)
    return {"status": "success", "id": mid}

@app.delete("/api/memory/{memory_id}")
async def delete_memory_entry(memory_id: int):
    ok = memory.delete_episodic_memory(memory_id)
    return {"status": "success" if ok else "not_found"}

@app.post("/api/memory/clear")
async def clear_memory():
    memory.clear_episodic_memory()
    return {"status": "success"}

@app.post("/api/memory/clear-category")
async def clear_category(request: CategoryToggleRequest):
    """Delete all entries that belong to a specific category."""
    types = MEMORY_CATEGORIES.get(request.category, {}).get("types", [])
    if not types and request.category != "other":
        return {"status": "not_found"}
    import sqlite3 as _sql
    with _sql.connect(memory.db_path) as conn:
        if request.category == "other":
            known = [t for v in MEMORY_CATEGORIES.values() for t in v["types"]]
            placeholders = ",".join("?" * len(known))
            conn.execute(f"DELETE FROM episodic_memory WHERE event_type NOT IN ({placeholders})", known)
        else:
            placeholders = ",".join("?" * len(types))
            conn.execute(f"DELETE FROM episodic_memory WHERE event_type IN ({placeholders})", types)
        conn.commit()
    return {"status": "success"}

@app.post("/api/memory/toggle")
async def toggle_memory(request: MemoryToggleRequest):
    global memory_enabled
    memory_enabled = request.enabled
    skill_manager.security.policy["memory_enabled"] = memory_enabled
    skill_manager.security._save_policy(skill_manager.security.policy)
    if mello_chat:
        mello_chat.memory_enabled = memory_enabled
    return {"status": "success", "enabled": memory_enabled}

@app.post("/api/memory/category/toggle")
async def toggle_category(request: CategoryToggleRequest):
    cats = skill_manager.security.policy.get("memory_categories", {})
    cats[request.category] = request.enabled
    skill_manager.security.policy["memory_categories"] = cats
    skill_manager.security._save_policy(skill_manager.security.policy)
    if mello_chat:
        mello_chat.disabled_categories = {k for k, v in cats.items() if not v}
    return {"status": "success"}

@app.get("/api/reports")
async def get_reports():
    if not os.path.exists(watch_path):
        return {"reports": []}
    files = os.listdir(watch_path)
    reports = []
    for f in files:
        f_path = os.path.join(watch_path, f)
        if os.path.isfile(f_path):
            reports.append({
                "name": f,
                "size": os.path.getsize(f_path),
                "modified": os.path.getmtime(f_path)
            })
    return {"reports": reports}

@app.get("/api/security")
async def get_security():
    return {"policy": skill_manager.security.policy}

@app.get("/api/apps/installed")
async def get_installed_apps():
    try:
        # On Windows, we can use PowerShell to list common apps
        cmd = "Get-StartApps | ConvertTo-Json"
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
        if result.returncode == 0:
            return {"apps": json.loads(result.stdout)}
        return {"apps": []}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/system/pick-folder")
async def pick_folder():
    """Open a native folder-picker dialog and return the chosen path."""
    import threading
    result: dict = {}

    def _open_picker():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", 1)
            chosen = filedialog.askdirectory(title="Select Folder to Allow")
            root.destroy()
            result["path"] = chosen if chosen else None
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=_open_picker, daemon=True)
    t.start()
    t.join(timeout=60)
    return {"path": result.get("path")}

@app.get("/api/workspace")
async def get_workspace():
    """Return watch folder file tree with memory-tracked status for the file map."""
    if not os.path.exists(watch_path):
        return {"tree": [], "root": watch_path, "enabled": memory_enabled}

    # Collect filenames already recorded in memory under file event types
    known: set = set()
    entries = memory.search_episodic_memory("", limit=5000)
    for e in entries:
        if e[2] in ("file_detected", "file_created", "file_moved"):
            desc = e[3]
            for pfx in ("File detected: ", "File created: ", "File moved: ",
                        "Moved to: ", "Moved file: "):
                if desc.startswith(pfx):
                    known.add(os.path.basename(desc[len(pfx):].strip()))
                    break

    def scan(path):
        items = []
        try:
            names = sorted(
                os.listdir(path),
                key=lambda n: (os.path.isfile(os.path.join(path, n)), n.lower())
            )
            for name in names:
                full = os.path.join(path, name)
                if os.path.isdir(full):
                    children = scan(full)
                    file_count = sum(1 for c in children if c["type"] == "file")
                    items.append({
                        "type": "folder",
                        "name": name,
                        "children": children,
                        "file_count": file_count,
                    })
                else:
                    items.append({
                        "type": "file",
                        "name": name,
                        "known": name in known,
                        "size": os.path.getsize(full),
                    })
        except PermissionError:
            pass
        return items

    return {"tree": scan(watch_path), "root": watch_path, "enabled": memory_enabled}

@app.post("/api/system/terminal")
async def open_terminal():
    """Open a new terminal window and run the active model."""
    import platform as _platform
    model = mello_chat.model if mello_chat else "qwen3.5:4b"
    cmd   = f"ollama run {model}"
    try:
        if _platform.system() == "Windows":
            # Opens a new cmd window that stays open with the command running
            subprocess.Popen(
                ["cmd", "/c", "start", "cmd", "/k", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        elif _platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", "-a", "Terminal", "--args", "-e", cmd])
        else:  # Linux
            subprocess.Popen(["x-terminal-emulator", "-e", cmd])
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "success", "command": cmd}

@app.post("/api/system/shutdown")
async def shutdown_mello():
    print("\n[Shutdown Signal Received from Dashboard]")
    # We'll use a delayed exit to allow the response to reach the client
    async def delayed_shutdown():
        await asyncio.sleep(1)
        os._exit(0)
    asyncio.create_task(delayed_shutdown())
    return {"status": "success", "message": "Mello is shutting down..."}

class ModelPullRequest(BaseModel):
    name: str

@app.post("/api/models/pull")
async def pull_model(request: ModelPullRequest):
    try:
        ollama.pull(request.name)
        return {"status": "success", "message": f"Started pulling {request.name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/models/status")
async def get_model_status():
    """Return model availability, Ollama connectivity, and RAM state."""
    active = mello_chat.model if mello_chat else "qwen3.5:4b"

    def base(name): return name.split(':')[0].lower()

    ollama_running = False
    is_live        = False
    running        = []

    try:
        list_result    = ollama.list()
        ollama_running = True
        if hasattr(list_result, 'models'):
            installed = [m.model for m in list_result.models]
        elif isinstance(list_result, dict):
            installed = [m.get('model', '') for m in list_result.get('models', [])]
        else:
            installed = []
        is_live = any(base(active) == base(m) for m in installed)
    except Exception:
        pass   # ollama_running stays False

    if ollama_running:
        try:
            ps_result = ollama.ps()
            if hasattr(ps_result, 'models'):
                running = [m.model for m in ps_result.models]
            elif isinstance(ps_result, dict):
                running = [m.get('model', '') for m in ps_result.get('models', [])]
        except Exception:
            pass

    return {
        "active_model":   active,
        "is_live":        is_live,
        "ollama_running": ollama_running,
        "running":        running,
    }

@app.post("/api/models/start")
async def start_model(request: ModelPullRequest):
    """Start Ollama if needed, then warm up the requested model."""
    import time
    import platform as _platform

    name = request.name or (mello_chat.model if mello_chat else "qwen3.5:4b")
    if mello_chat:
        mello_chat.model = name

    def _ensure_ollama_and_warmup():
        # ── Step 1: Start Ollama if it is not reachable ──────────────────
        try:
            ollama.list()
            print("[Ollama] Already running.")
        except Exception:
            print("[Ollama] Not running — launching 'ollama serve'…")
            try:
                kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
                if _platform.system() == "Windows":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(["ollama", "serve"], **kwargs)
            except FileNotFoundError:
                print("[Ollama] 'ollama' executable not found. Is Ollama installed?")
                return

            # Wait up to 20 s for the service to become ready
            for attempt in range(20):
                time.sleep(1)
                try:
                    ollama.list()
                    print(f"[Ollama] Service ready after {attempt + 1}s.")
                    break
                except Exception:
                    pass
            else:
                print("[Ollama] Service did not start in time.")
                return

        # ── Step 2: Load the model into memory ───────────────────────────
        try:
            print(f"[Ollama] Loading model '{name}'…")
            ollama.generate(model=name, prompt="hi", keep_alive="30m")
            print(f"[Ollama] Model '{name}' is live.")
        except Exception as e:
            print(f"[Ollama] Failed to load model: {e}")

    threading.Thread(target=_ensure_ollama_and_warmup, daemon=True).start()
    return {"status": "starting", "model": name}

@app.post("/api/models/select")
async def select_model(request: ModelPullRequest):
    """Switch which model Mello uses for chat, without loading it."""
    if mello_chat:
        mello_chat.model = request.name
    return {"status": "success", "model": request.name}

import ast as _ast

class SkillCreateRequest(BaseModel):
    name: str
    description: str
    code: str = ""   # Python class code generated by AI or written manually

class SkillGenerateRequest(BaseModel):
    name: str
    description: str

# ── AI-powered skill code generator ──────────────────────────────────────────

@app.post("/api/skills/ai-generate")
async def ai_generate_skill(request: SkillGenerateRequest):
    """Ask the active LLM to write a Python skill class for the given spec."""
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', request.name).lower().strip('_')
    class_name = ''.join(w.capitalize() for w in safe_name.split('_')) + "Skill"

    prompt = f"""You are writing a Python plugin class for an AI assistant called Mello.

SKILL SPEC
  name        : {safe_name}
  class name  : {class_name}
  description : {request.description}

RULES — follow exactly:
1. Extend BaseSkill (already available in scope, do NOT import it).
2. Set these class attributes:
     name        = "{safe_name}"
     description = "{request.description}"
     category    = "custom"
3. Implement:  def execute(self, params: dict) -> str
4. First line of execute must be:
     if not self.enabled: return super().execute(params)
5. Use only these stdlib modules (already available, do NOT re-import):
     os  re  json  subprocess  platform  datetime  shutil
   For HTTP use:  import urllib.request, urllib.parse  (inside the method)
6. Always wrap the core logic in try/except and return an error string on failure.
7. Return ONLY the raw Python class code — no markdown fences, no explanations.

Write the class now:"""

    try:
        model = mello_chat.model if mello_chat else "qwen3.5:4b"
        resp  = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        code = resp["message"]["content"].strip()
        # Strip any markdown code fences the model may have added
        code = re.sub(r"^```[a-zA-Z]*\s*", "", code, flags=re.MULTILINE)
        code = re.sub(r"^```\s*$",          "", code, flags=re.MULTILINE)
        code = code.strip()
        return {"status": "success", "code": code, "skill_name": safe_name}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

# ── Actual skill installer (writes file + hot-reloads) ────────────────────────

@app.post("/api/skills/create")
async def create_skill(request: SkillCreateRequest):
    safe_name  = re.sub(r"[^a-zA-Z0-9]", "_", request.name).lower().strip("_") or "custom_skill"
    code       = request.code.strip()

    if not code:
        return {"status": "error", "message": "No code provided. Use /api/skills/ai-generate first."}

    # Syntax-check before saving
    try:
        _ast.parse(code)
    except SyntaxError as exc:
        return {"status": "error", "message": f"Syntax error in generated code: {exc}"}

    import pathlib
    custom_dir = pathlib.Path(__file__).parent / "skills" / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    skill_file = custom_dir / f"{safe_name}.py"
    skill_file.write_text(code, encoding="utf-8")

    # Hot-reload into the running SkillManager
    loaded = skill_manager.load_custom_skills()
    # Rebuild the system-prompt manifest so the AI knows about the new skill
    if mello_chat:
        mello_chat._build_system_prompt()

    if safe_name in loaded or any(safe_name in n for n in loaded):
        return {
            "status":  "success",
            "message": f"✅ Skill '{safe_name}' installed and live! ({skill_file})",
            "loaded":  loaded,
        }
    return {
        "status":  "warning",
        "message": f"File saved to {skill_file} but no BaseSkill subclass was detected — check the code.",
        "loaded":  loaded,
    }

# ── App Settings (persisted JSON) ────────────────────────────────────────────
_SETTINGS_FILE = "mello_settings.json"

def _load_settings() -> dict:
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_settings(data: dict):
    try:
        with open(_SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Settings] Save error: {e}")

class SettingsSaveRequest(BaseModel):
    settings: dict

@app.get("/api/settings")
async def get_settings_endpoint():
    return _load_settings()

@app.post("/api/settings")
async def save_settings_endpoint(request: SettingsSaveRequest):
    global _stt_model, _stt_backend, _stt_model_name
    _save_settings(request.settings)
    new_model = request.settings.get("micModel", "tiny")
    with _stt_lock:
        if new_model != _stt_model_name:
            # Force a fresh model load on next transcription
            _stt_model   = None
            _stt_backend = None
    return {"status": "success"}


# ── Offline Speech-to-Text (Whisper) ─────────────────────────────────────────
_stt_model      = None
_stt_backend    = None          # "faster_whisper" | "openai_whisper" | "none"
_stt_model_name = "tiny"
_stt_lock       = threading.Lock()

def _load_stt() -> str:
    """Lazy-load the best available local Whisper backend (called in a thread)."""
    global _stt_model, _stt_backend, _stt_model_name
    with _stt_lock:
        requested = _load_settings().get("micModel", "tiny")
        if _stt_backend is not None and _stt_model_name == requested:
            return _stt_backend   # already loaded and correct model
        # Reset if model changed
        _stt_model   = None
        _stt_backend = None
        _stt_model_name = requested

        # 1) faster-whisper (preferred — small RAM, int8 quantised)
        try:
            from faster_whisper import WhisperModel
            _stt_model   = WhisperModel(requested, device="cpu", compute_type="int8")
            _stt_backend = "faster_whisper"
            print(f"[STT] faster-whisper ready  ({requested} / CPU / int8)")
            return _stt_backend
        except ImportError:
            pass
        # 2) openai-whisper fallback
        try:
            import whisper as _ow
            _stt_model   = _ow.load_model(requested)
            _stt_backend = "openai_whisper"
            print(f"[STT] openai-whisper ready  ({requested})")
            return _stt_backend
        except ImportError:
            pass

        _stt_backend = "none"
        print("[STT] No Whisper backend — install: pip install faster-whisper")
        return _stt_backend

def _do_transcribe(path: str, language: str = "auto") -> str:
    """Run transcription synchronously (called via asyncio.to_thread)."""
    lang = None if (not language or language == "auto") else language
    if _stt_backend == "faster_whisper":
        segments, _ = _stt_model.transcribe(path, beam_size=1, language=lang)
        return " ".join(s.text for s in segments).strip()
    elif _stt_backend == "openai_whisper":
        kwargs: dict = {}
        if lang:
            kwargs["language"] = lang
        result = _stt_model.transcribe(path, **kwargs)
        return result["text"].strip()
    return ""

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Offline speech-to-text — accepts webm/wav/ogg. Model & language from settings."""
    settings = _load_settings()
    language = settings.get("micLanguage", "auto")

    backend = await asyncio.to_thread(_load_stt)
    if backend == "none":
        return {"error": "no_stt_backend", "install": "pip install faster-whisper", "text": ""}

    data = await audio.read()
    if not data:
        return {"error": "no_speech", "text": ""}

    ext = ".webm"
    ct  = audio.content_type or ""
    if "ogg"  in ct: ext = ".ogg"
    elif "wav" in ct: ext = ".wav"
    elif "mp4" in ct: ext = ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        text = await asyncio.to_thread(_do_transcribe, tmp_path, language)
        return {"text": text} if text else {"error": "no_speech", "text": ""}
    except Exception as exc:
        print(f"[STT] Transcription error: {exc}")
        return {"error": str(exc), "text": ""}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# Static files (styles, scripts)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_server(mem, chat, skills, path):
    global memory, mello_chat, skill_manager, watch_path, memory_enabled
    memory        = mem
    mello_chat    = chat
    skill_manager = skills
    watch_path    = path
    # Load persisted memory toggle from policy
    memory_enabled = skills.security.policy.get("memory_enabled", True)
    if mello_chat:
        mello_chat.memory_enabled = memory_enabled
