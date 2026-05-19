import json
import os

class SecurityLayer:
    def __init__(self, policy_path="security_policy.json"):
        self.policy_path = policy_path
        self.policy = self._load_policy()

    def _load_policy(self):
        if os.path.exists(self.policy_path):
            return json.load(open(self.policy_path, 'r'))
        default_policy = {
            "allowed_folders": [
                os.path.expanduser("~"),
                "./test_watch",
                "./screenshots",
            ],
            "allowed_apps": ["calc", "notepad", "cmd", "explorer", "chrome", "msedge"],
            "allow_all_commands": False
        }
        self._save_policy(default_policy)
        return default_policy

    def _save_policy(self, policy):
        with open(self.policy_path, 'w') as f:
            json.dump(policy, f, indent=4)

    def is_path_allowed(self, path):
        abs_path = os.path.abspath(os.path.expanduser(path))
        for allowed in self.policy.get("allowed_folders", []):
            abs_allowed = os.path.abspath(os.path.expanduser(allowed))
            if abs_path.startswith(abs_allowed):
                return True
        return False

    def is_app_allowed(self, app_name):
        return any(a.lower() == app_name.lower() for a in self.policy.get("allowed_apps", []))

    def allow_app(self, app_name):
        apps = self.policy.get("allowed_apps", [])
        if not any(a.lower() == app_name.lower() for a in apps):
            apps.append(app_name)
            self.policy["allowed_apps"] = apps
            self._save_policy(self.policy)

    def deny_app(self, app_name):
        self.policy["allowed_apps"] = [
            a for a in self.policy.get("allowed_apps", [])
            if a.lower() != app_name.lower()
        ]
        self._save_policy(self.policy)

    def is_command_allowed(self, command):
        if self.policy.get("allow_all_commands", False):
            return True
        # Very basic check: only allow commands that don't look dangerous
        dangerous_keywords = ["rm ", "del ", "format ", "shutdown", "wget", "curl"]
        for kw in dangerous_keywords:
            if kw in command.lower():
                return False
        return True
