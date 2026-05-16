import os
import shutil
import json
import subprocess
import platform

class BaseSkill:
    """Base class for all Mello Skills"""
    name = "base_skill"
    description = "Base skill description"
    enabled = True
    
    def execute(self, params):
        if not self.enabled:
            return f"Error: Skill '{self.name}' is currently disabled."
        raise NotImplementedError("Skills must implement execute()")

class FileSystemSkill(BaseSkill):
    name = "file_system"
    description = "Manage folders and move files"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
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
        if not self.enabled: return super().execute(params)
        path = params.get("path")
        if not os.path.exists(path):
            return f"Error: File {path} not found."
            
        # Security: check extension
        if not path.lower().endswith(('.txt', '.csv', '.md', '.json', '.py', '.log')):
            return "Error: Unsupported file type."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(2048) # Limit read size
            return content

class AppAutomationSkill(BaseSkill):
    name = "app_automation"
    description = "Open applications"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        app_name = params.get("app_name")
        # Common Windows aliases
        aliases = {
            "calculator": "calc",
            "notepad": "notepad",
            "command prompt": "cmd",
            "cmd": "cmd",
            "explorer": "explorer",
            "chrome": "chrome",
            "edge": "msedge"
        }
        
        executable = aliases.get(app_name.lower(), app_name)
        
        try:
            if platform.system() == "Windows":
                # Using 'start' is generally best for apps in PATH
                subprocess.Popen(f"start {executable}", shell=True)
            elif platform.system() == "Darwin": # macOS
                subprocess.Popen(["open", "-a", executable])
            else: # Linux
                subprocess.Popen([executable])
            return f"Attempted to open: {executable}"
        except Exception as e:
            return f"Error opening app: {str(e)}"

class ShellExecutionSkill(BaseSkill):
    name = "shell_execution"
    description = "Run shell commands (PowerShell/CMD)"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        command = params.get("command")
        
        # Translation Layer: Convert common Linux commands to Windows equivalents
        if platform.system() == "Windows":
            if command.startswith("touch "):
                file_path = command.replace("touch ", "").strip()
                command = f"New-Item -Path {file_path} -ItemType File -Force"
            elif command.startswith("ls "):
                command = command.replace("ls ", "dir ")
            elif command.startswith("rm "):
                command = command.replace("rm ", "Remove-Item ")

        try:
            # Note: In a production app, we would add strict security checks here
            result = subprocess.run(
                ["powershell", "-Command", command] if platform.system() == "Windows" else [command],
                capture_output=True,
                text=True,
                shell=True
            )
            output = result.stdout if result.returncode == 0 else result.stderr
            if not output and result.returncode == 0:
                return "Command executed successfully (no output)."
            return f"Command executed. Output:\n{output[:1000]}"
        except Exception as e:
            return f"Error executing command: {str(e)}"

import pyautogui
import datetime

class VisionSkill(BaseSkill):
    name = "vision"
    description = "Take a screenshot to 'see' the desktop"
    
    def execute(self, params):
        if not self.enabled: return super().execute(params)
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            # Ensure a screenshots folder exists
            os.makedirs("screenshots", exist_ok=True)
            path = os.path.join("screenshots", filename)
            pyautogui.screenshot(path)
            return f"Screenshot saved to {path}. I can now 'see' your desktop state."
        except Exception as e:
            return f"Error taking screenshot: {str(e)}"

from ..security import SecurityLayer

class SkillManager:
    """Loads and manages Mello's modular skills with a Security Layer"""
    def __init__(self):
        self.security = SecurityLayer()
        self.skills = {
            "mkdir": FileSystemSkill(),
            "move": FileSystemSkill(),
            "read_file": FileReadSkill(),
            "open_app": AppAutomationSkill(),
            "run_command": ShellExecutionSkill(),
            "screenshot": VisionSkill()
        }

    def toggle_skill(self, skill_name, state: bool):
        if skill_name in self.skills:
            self.skills[skill_name].enabled = state
            return True
        return False

    def get_skill_manifest(self):
        """Returns a string description of all available skills for the LLM prompt"""
        manifest = "Available Skills:\n"
        for name, skill in self.skills.items():
            if skill.enabled:
                if name == "mkdir": manifest += "- mkdir: Create a folder. Params: { 'path': 'string' }\n"
                elif name == "move": manifest += "- move: Move a file. Params: { 'source': 'string', 'destination': 'string' }\n"
                elif name == "read_file": manifest += "- read_file: Read file content. Params: { 'path': 'string' }\n"
                elif name == "open_app": manifest += "- open_app: Open an application. Params: { 'app_name': 'string' }\n"
                elif name == "run_command": manifest += "- run_command: Run a shell command. Params: { 'command': 'string' }\n"
                elif name == "screenshot": manifest += "- screenshot: Take a screenshot of the current screen. Params: {}\n"
        return manifest

    def run_skill(self, action, params):
        # 1. Permission Checks
        if action in ["mkdir", "move", "read_file"]:
            path = params.get("path") or params.get("source") or params.get("destination")
            if path and not self.security.is_path_allowed(path):
                return f"Security Error: Access to path '{path}' is denied by policy."
        
        if action == "open_app":
            app_name = params.get("app_name")
            if not self.security.is_app_allowed(app_name):
                return f"Security Error: Application '{app_name}' is not in the allowed list."
        
        if action == "run_command":
            command = params.get("command")
            if not self.security.is_command_allowed(command):
                return f"Security Error: Command '{command}' contains restricted keywords or is disallowed."

        # 2. Execution
        skill = self.skills.get(action)
        if skill:
            return skill.execute(params)
        return f"Skill for action '{action}' not found."
