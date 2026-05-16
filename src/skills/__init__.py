import os
import shutil
import json

class BaseSkill:
    """Base class for all Mello Skills"""
    name = "base_skill"
    description = "Base skill description"
    
    def execute(self, params):
        raise NotImplementedError("Skills must implement execute()")

class FileSystemSkill(BaseSkill):
    name = "file_system"
    description = "Manage folders and move files"
    
    def execute(self, params):
        action = params.get("action")
        path = params.get("path")
        
        if action == "mkdir":
            os.makedirs(path, exist_ok=True)
            return f"Created folder: {path}"
        elif action == "move":
            src = params.get("source")
            dst = params.get("destination")
            shutil.move(src, dst)
            return f"Moved {src} to {dst}"
        return f"Unknown action: {action}"

class FileReadSkill(BaseSkill):
    name = "file_reader"
    description = "Read contents of text-based files"
    
    def execute(self, params):
        path = params.get("path")
        if not os.path.exists(path):
            return f"Error: File {path} not found."
            
        # Security: check extension
        if not path.lower().endswith(('.txt', '.csv', '.md', '.json', '.py', '.log')):
            return "Error: Unsupported file type."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(2048) # Limit read size
            return content

class SkillManager:
    """Loads and manages Mello's modular skills"""
    def __init__(self):
        self.skills = {
            "mkdir": FileSystemSkill(),
            "move": FileSystemSkill(),
            "read_file": FileReadSkill()
        }

    def get_skill_manifest(self):
        """Returns a string description of all available skills for the LLM prompt"""
        manifest = "Available Skills:\n"
        manifest += "- mkdir: Create a folder. Params: { 'path': 'string' }\n"
        manifest += "- move: Move a file. Params: { 'source': 'string', 'destination': 'string' }\n"
        manifest += "- read_file: Read file content. Params: { 'path': 'string' }\n"
        return manifest

    def run_skill(self, action, params):
        skill = self.skills.get(action)
        if skill:
            # Normalize params if they are nested
            return skill.execute(params)
        return f"Skill for action '{action}' not found."
