import os
import shutil

class ExecutionEngine:
    def __init__(self, memory):
        self.memory = memory

    def execute_action(self, action_json):
        """
        Executes a validated action.
        Expected format: {"action": "mkdir", "path": "path/to/dir"}
        """
        action = action_json.get("action")
        try:
            if action == "mkdir":
                path = action_json.get("path")
                os.makedirs(path, exist_ok=True)
                return f"Successfully created folder: {path}"
            
            elif action == "move":
                src = action_json.get("source")
                dst = action_json.get("destination")
                shutil.move(src, dst)
                return f"Moved file from {src} to {dst}"
            
            elif action == "read_file":
                path = action_json.get("path")
                # Safety: check if it's a text/csv file
                if not path.endswith(('.txt', '.csv', '.md', '.json', '.py', '.log')):
                    return "Error: Unsupported file type for direct reading."
                
                with open(path, 'r', encoding='utf-8') as f:
                    # Read only first 2KB to avoid context overflow
                    content = f.read(2048)
                    return f"Content of {path}:\n{content}"
            
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Error executing {action}: {str(e)}"
