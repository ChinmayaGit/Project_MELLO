from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import asyncio
import threading
import os
import ollama
import subprocess
from .memory import MemorySystem
from .chat import MelloChat
from .skills import SkillManager
from .compressor import MemoryCompressor

app = FastAPI()

# Global instances (will be initialized in main.py or startup)
memory = None
mello_chat = None
skill_manager = None
watch_path = None

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
        {"name": name, "enabled": skill.enabled, "desc": skill.description}
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
    """Return the active model name and whether it is currently loaded in Ollama memory."""
    active = mello_chat.model if mello_chat else "qwen3.5:4b"
    try:
        ps_result = ollama.ps()
        if hasattr(ps_result, 'models'):
            running = [m.model for m in ps_result.models]
        elif isinstance(ps_result, dict):
            running = [m.get('model', '') for m in ps_result.get('models', [])]
        else:
            running = []
        # Match on base name (ignore tag differences like :latest vs :4b)
        def base(name): return name.split(':')[0].lower()
        is_live = any(base(active) == base(r) for r in running)
    except Exception:
        is_live = False
        running = []
    return {"active_model": active, "is_live": is_live, "running": running}

@app.post("/api/models/start")
async def start_model(request: ModelPullRequest):
    """Warm up (load into memory) a model. Updates the active chat model too."""
    name = request.name or (mello_chat.model if mello_chat else "qwen3.5:4b")
    if mello_chat:
        mello_chat.model = name

    def _warmup():
        try:
            ollama.generate(model=name, prompt='hi', keep_alive='30m')
        except Exception as e:
            print(f"[Model Warmup] {e}")

    threading.Thread(target=_warmup, daemon=True).start()
    return {"status": "starting", "model": name}

@app.post("/api/models/select")
async def select_model(request: ModelPullRequest):
    """Switch which model Mello uses for chat, without loading it."""
    if mello_chat:
        mello_chat.model = request.name
    return {"status": "success", "model": request.name}

class SkillCreateRequest(BaseModel):
    name: str
    description: str

@app.post("/api/skills/create")
async def create_skill(request: SkillCreateRequest):
    # This is a simplified version that just adds it to the manifest/list
    # In a real app, we'd write a new .py file to src/skills/
    try:
        # For now, let's just simulate adding it
        return {"status": "success", "message": f"Skill '{request.name}' registered (Simulation)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Static files (styles, scripts)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_server(mem, chat, skills, path):
    global memory, mello_chat, skill_manager, watch_path
    memory = mem
    mello_chat = chat
    skill_manager = skills
    watch_path = path
