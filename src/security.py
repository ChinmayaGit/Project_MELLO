import json
import os

class SecurityLayer:
    def __init__(self, policy_path="security_policy.json"):
        self.policy_path = policy_path
        self.policy = self._load_policy()

    def _load_policy(self):
        if os.path.exists(self.policy_path):
            with open(self.policy_path, 'r') as f:
                return json.load(f)
        else:
            # Default restrictive policy
            default_policy = {
                "allowed_folders": ["./test_watch", "./screenshots"],
                "allowed_apps": ["calc", "notepad", "cmd", "explorer"],
                "allow_all_commands": False
            }
            self._save_policy(default_policy)
            return default_policy

    def _save_policy(self, policy):
        with open(self.policy_path, 'w') as f:
            json.dump(policy, f, indent=4)

    def is_path_allowed(self, path):
        abs_path = os.path.abspath(path)
        for allowed in self.policy.get("allowed_folders", []):
            abs_allowed = os.path.abspath(allowed)
            if abs_path.startswith(abs_allowed):
                return True
        return False

    def is_app_allowed(self, app_name):
        return app_name.lower() in [a.lower() for a in self.policy.get("allowed_apps", [])]

    def is_command_allowed(self, command):
        if self.policy.get("allow_all_commands", False):
            return True
        # Very basic check: only allow commands that don't look dangerous
        dangerous_keywords = ["rm ", "del ", "format ", "shutdown", "wget", "curl"]
        for kw in dangerous_keywords:
            if kw in command.lower():
                return False
        return True
