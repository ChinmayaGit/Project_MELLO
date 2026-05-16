import os
import time
from dotenv import load_dotenv
from src.memory import MemorySystem
from src.classifier import Classifier
from src.events import start_watching
from src.chat import MelloChat
from src.skills import SkillManager
import json
import re

def main():
    load_dotenv()
    
    # Configuration
    watch_path = os.getenv("WATCH_PATH", "./test_watch")
    db_path = os.getenv("DB_PATH", "mello_memory.db")
    classifier_model = os.getenv("CLASSIFIER_MODEL", "qwen3.5:0.8b")
    main_model = os.getenv("MAIN_MODEL", "qwen3.5:4b")
    think_enabled = os.getenv("THINK_ENABLED", "true").lower() == "true"
    
    # Ensure watch path exists
    if not os.path.exists(watch_path):
        os.makedirs(watch_path, exist_ok=True)
        print(f"Created watch directory: {watch_path}")

    # Initialize Systems
    print("\n--- Initializing Mello (Phase 2) ---")
    memory = MemorySystem(db_path)
    classifier = Classifier(model=classifier_model)
    mello_chat = MelloChat(memory, model=main_model, think_enabled=think_enabled)
    skill_manager = SkillManager()
    
    print(f"Memory DB: {db_path}")
    print(f"Skills Loaded: {list(skill_manager.skills.keys())}")
    print(f"Thinking Process: {'Enabled' if think_enabled else 'Disabled'}")
    print(f"Watching: {watch_path}")
    
    # Start the event watcher (Non-blocking)
    observer = start_watching(watch_path, memory, classifier)
    
    print("\n--- Mello is Active ---")
    print("Modular Skill Engine online.")
    print("Type your message below (type 'exit' to stop).")
    
    try:
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Mello: Goodbye! Powering down systems...")
                break
            
            # Chat with Mello (Streaming)
            print("\nMello: ", end="", flush=True)
            full_response = ""
            for chunk in mello_chat.chat_stream(user_input):
                print(chunk, end="", flush=True)
                full_response += chunk
            print() # New line after stream ends
            
            # Check for skill execution in the response
            action_match = re.search(r'\{.*"action":.*\}', full_response, re.DOTALL)
            if action_match:
                try:
                    action_json = json.loads(action_match.group(0))
                    action = action_json.get("action")
                    print(f"\n[Skill Execution: {action}]")
                    
                    result = skill_manager.run_skill(action, action_json)
                    print(f"[Result: {result[:100]}...]" if len(result) > 100 else f"[Result: {result}]")
                    
                    # Update memory
                    memory.add_episodic_memory("skill_executed", result[:200], action_json)
                    
                    # Handle re-analysis for read_file
                    if action == "read_file":
                        print("\nMello is analyzing the data... ", end="", flush=True)
                        for chunk in mello_chat.chat_stream(f"I have read the file. Content:\n{result}\n\nPlease proceed."):
                            print(chunk, end="", flush=True)
                        print()
                except Exception as e:
                    print(f"\n[Skill Error: {str(e)}]")
            
    except KeyboardInterrupt:
        print("\nMello: Session interrupted. Shutting down...")
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    main()
