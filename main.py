import os
import logging
import uvicorn
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
from src.memory import MemorySystem
from src.classifier import Classifier
from src.events import start_watching
from src.chat import MelloChat
from src.skills import SkillManager
from src.compressor import MemoryCompressor
from src.server import app, init_server

def main():
    load_dotenv()
    
    # Configuration
    watch_path = os.getenv("WATCH_PATH", "./test_watch")
    db_path = os.getenv("DB_PATH", "mello_memory.db")
    classifier_model = os.getenv("CLASSIFIER_MODEL", "qwen3.5:0.8b")
    main_model = os.getenv("MAIN_MODEL", "qwen3.5:4b")
    think_enabled = os.getenv("THINK_ENABLED", "true").lower() == "true"
    
    # Ensure folders exist
    os.makedirs(watch_path, exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)

    # Initialize Core Systems
    print("\n--- Initializing Mello Web Dashboard ---")
    memory = MemorySystem(db_path)
    classifier = Classifier(model=classifier_model)
    mello_chat = MelloChat(memory, model=main_model, think_enabled=think_enabled, watch_path=watch_path)
    skill_manager = SkillManager()
    mem_enabled   = skill_manager.security.policy.get("memory_enabled", True)

    # Start the event watcher — skip initial scan if memory is disabled
    observer = start_watching(watch_path, memory, classifier,
                              scan_on_start=mem_enabled)
    
    # Initialize Web Server with core instances
    init_server(memory, mello_chat, skill_manager, watch_path)
    
    print(f"Mello is active at http://localhost:8000")
    print(f"Watching: {watch_path}")
    
    try:
        # Run the web server
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        print("\nMello: Shutting down...")
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    main()
