import os
import subprocess
import platform
import ollama
import json
import re
import time
import logging
from .memory import MemorySystem
from .skills import SkillManager

log = logging.getLogger("mello.chat")

# Maps category keys → event_type strings (must stay in sync with server.py)
_CATEGORY_TYPES = {
    "files":  {"file_detected", "file_created", "file_moved"},
    "skills": {"skill_execution", "skill_executed", "action_executed"},
    "chat":   {"chat_message"},
}

class MelloChat:
    def __init__(self, memory: MemorySystem, model="qwen3.5:4b", think_enabled=True, watch_path="./test_watch"):
        self.memory = memory
        self.model = model
        self.think_enabled = think_enabled
        self.watch_path = os.path.abspath(watch_path)
        self.skill_manager = SkillManager()
        self.memory_enabled      = True   # toggled by server
        self.disabled_categories = set()  # set of category keys e.g. {"files"}
        self.messages = []
        self._build_system_prompt()

    def _build_system_prompt(self):
        think_note = "Respond directly and concisely." if not self.think_enabled else ""
        system = f"""You are Mello, a local-first AI assistant. {think_note}

ENVIRONMENT:
- Watch folder (default location for new files/folders): {self.watch_path}
- Always use FULL ABSOLUTE paths in skill JSON. Never use bare names like "auto" or "test".
- If the user does not specify a location, create inside the watch folder: {self.watch_path}
- Example: if user says "create folder reports", use path "{self.watch_path}\\reports"
- You CAN access any folder on the local file system that the user specifies.

{self.skill_manager.get_skill_manifest()}

SKILL CREATION — YOU CAN BUILD NEW SKILLS:
You are fully capable of writing Python code and creating new skills for yourself.
When asked to create a new skill, write a complete Python class and output it as a
write_skill JSON block:
  {{"action": "write_skill", "skill_name": "snake_case_name", "description": "...",
    "category": "custom",
    "code": "class MySkill(BaseSkill):\\n    name = \\"snake_case_name\\"\\n    ..."}}

Rules for the Python class:
- Extend BaseSkill (available in scope — do NOT import it)
- Attributes: name (snake_case), description, category = "custom"
- Implement: def execute(self, params): -> str
- First line: if not self.enabled: return super().execute(params)
- Use only stdlib: os re json subprocess platform datetime shutil urllib.request urllib.parse
- Wrap logic in try/except; return error strings starting with "Error:"
- After the write_skill block the skill is IMMEDIATELY live — confirm it to the user.

RULES:
1. To use a skill, output a JSON block on its own line.
2. Use mkdir for folders, create_file for files.
3. Always use absolute paths.
4. After any JSON block, confirm what you did in plain text.
5. SORTING: Always use the sort skill for organise/sort requests.
6. For sort preview add "dry_run": true.
7. NEVER say you cannot create skills — you CAN write and install them."""
        if self.messages:
            self.messages[0]["content"] = system
        else:
            self.messages = [{"role": "system", "content": system}]

    def _disabled_event_types(self):
        """Return a set of event_type strings for all disabled categories."""
        disabled = set()
        for cat in self.disabled_categories:
            disabled |= _CATEGORY_TYPES.get(cat, set())
        return disabled

    def get_context(self, user_query=None):
        if not self.memory_enabled:
            return ""   # memory off — no context injected

        t0 = time.perf_counter()

        # Build the set of event types to exclude based on disabled categories
        excluded_types = self._disabled_event_types()

        # 1. Get recent context (Short-term memory)
        recent_events = self.memory.query_episodic_memory(limit=10)  # fetch more, then filter
        context_str = "Recent Events:\n"
        shown = 0
        for event in recent_events:
            event_type = event[2]
            if event_type in excluded_types:
                continue
            context_str += f"- {event[3]}\n"
            shown += 1
            if shown >= 3:
                break
        t1 = time.perf_counter()
        log.info(f"[PERF] SQLite episodic query: {(t1-t0)*1000:.1f}ms")

        # 2. Get semantically relevant context (Long-term/Semantic retrieval)
        if user_query:
            semantic_results = self.memory.semantic_search(user_query, limit=6)
            t2 = time.perf_counter()
            log.info(f"[PERF] ChromaDB semantic search: {(t2-t1)*1000:.1f}ms")
            if semantic_results and semantic_results['documents']:
                context_str += "\nRelevant Past Memories:\n"
                # metadatas[0] is parallel to documents[0]
                metas = (semantic_results.get('metadatas') or [[]])[0]
                for i, doc in enumerate(semantic_results['documents'][0]):
                    # Filter out excluded event types if metadata is available
                    if metas and i < len(metas):
                        meta_type = metas[i].get('type', '')
                        if meta_type in excluded_types:
                            continue
                    if doc not in context_str:
                        context_str += f"- {doc}\n"

        log.info(f"[PERF] get_context total: {(time.perf_counter()-t0)*1000:.1f}ms")
        return context_str

    def _ensure_ollama(self) -> bool:
        """Start Ollama if it is not reachable. Returns True when ready."""
        try:
            ollama.list()
            return True
        except Exception:
            log.info("[Ollama] Not running — launching 'ollama serve'…")
            try:
                kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
                if platform.system() == "Windows":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(["ollama", "serve"], **kwargs)
            except FileNotFoundError:
                log.error("[Ollama] 'ollama' executable not found. Is Ollama installed?")
                return False
            except Exception as exc:
                log.error(f"[Ollama] Could not launch: {exc}")
                return False

            for attempt in range(20):
                time.sleep(1)
                try:
                    ollama.list()
                    log.info(f"[Ollama] Service ready after {attempt + 1}s.")
                    return True
                except Exception:
                    pass
            log.error("[Ollama] Service did not start in time.")
            return False

    def chat_stream(self, user_input):
        self._build_system_prompt()

        t_start = time.perf_counter()

        # Make sure Ollama is running before we attempt any inference
        if not self._ensure_ollama():
            yield (
                "⚠️ **Ollama is not running** and could not be started automatically.\n\n"
                "Please:\n"
                "1. Open a terminal and run `ollama serve`\n"
                "2. Then try your message again."
            )
            return

        # Perform semantic retrieval based on the input
        context = self.get_context(user_input)

        user_message = {"role": "user", "content": f"Context: {context}\n\nUser: {user_input}"}
        self.messages.append(user_message)

        # Limit history to last 5 turns for max speed
        if len(self.messages) > 11:
            self.messages = [self.messages[0]] + self.messages[-10:]

        prompt_tokens = sum(len(m["content"]) for m in self.messages)
        log.info(f"[PERF] Prompt size: ~{prompt_tokens} chars across {len(self.messages)} messages")

        try:
            t_ollama = time.perf_counter()
            log.info(f"[PERF] Calling ollama.chat (model={self.model}, think={self.think_enabled})...")
            stream = ollama.chat(
                model=self.model,
                messages=self.messages,
                stream=True,
                think=self.think_enabled,
            )
            full_response = ""
            in_think_block = False
            first_token = True

            for chunk in stream:
                text = chunk['message']['content']
                full_response += text

                if first_token:
                    log.info(f"[PERF] Time to first token: {(time.perf_counter()-t_ollama)*1000:.1f}ms")
                    first_token = False

                if not self.think_enabled:
                    if "<think>" in text:
                        in_think_block = True
                        continue
                    if "</think>" in text:
                        in_think_block = False
                        continue
                    if not in_think_block:
                        yield text
                else:
                    yield text

            t_end = time.perf_counter()
            log.info(f"[PERF] Generation complete: {(t_end-t_ollama)*1000:.1f}ms total, ~{len(full_response)} chars")
            log.info(f"[PERF] Full request time (context+generation): {(t_end-t_start)*1000:.1f}ms")
            self.messages.append({"role": "assistant", "content": full_response})

            # Parse and execute any skill JSON blocks in the response
            skill_results = self._execute_skills(full_response)
            for result in skill_results:
                if self.memory_enabled:
                    self.memory.add_episodic_memory("skill_execution", result)
                yield f"\n\n**[Done]** {result}"

        except Exception as e:
            log.error(f"[PERF] ollama.chat error: {e}")
            yield f"Error: {str(e)}"

    def _write_skill_inline(self, data: dict) -> str:
        """Handle a write_skill JSON block emitted by the LLM — write file + hot-reload."""
        import ast as _ast, pathlib, re as _re

        skill_name = data.get("skill_name", "").strip()
        code       = data.get("code", "").strip()

        if not skill_name or not code:
            return "Error: write_skill requires 'skill_name' and 'code' fields."

        safe = _re.sub(r"[^a-zA-Z0-9]", "_", skill_name).lower().strip("_") or "custom_skill"

        # Strip accidental markdown fences
        code = _re.sub(r"^```[a-zA-Z]*\s*", "", code, flags=_re.MULTILINE)
        code = _re.sub(r"^```\s*$",          "", code, flags=_re.MULTILINE)
        code = code.strip()

        # Syntax check
        try:
            _ast.parse(code)
        except SyntaxError as exc:
            return f"Error: Syntax error in generated skill code — {exc}"

        custom_dir = pathlib.Path(__file__).parent / "skills" / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)
        skill_file = custom_dir / f"{safe}.py"
        skill_file.write_text(code, encoding="utf-8")

        loaded = self.skill_manager.load_custom_skills()
        self._build_system_prompt()   # refresh manifest with new skill

        log.info(f"[SKILL] write_skill saved {skill_file}, loaded: {loaded}")
        if loaded:
            return f"✅ Skill '{safe}' installed and live! I can now use it immediately."
        return f"⚠️ Skill file saved to {skill_file} but no BaseSkill subclass was found — check the code."

    def _execute_skills(self, response_text):
        """Parse LLM response for skill JSON blocks and execute them."""
        results = []
        seen    = set()

        # Use a broader pattern that allows embedded newlines (for code fields)
        for match in re.finditer(r'\{.*?\}', response_text, re.DOTALL):
            json_str = match.group().strip()
            if json_str in seen:
                continue
            seen.add(json_str)
            try:
                data   = json.loads(json_str)
                action = data.get("action")
                if not action:
                    continue

                # ── inline skill writer ──────────────────────────────────
                if action == "write_skill":
                    result = self._write_skill_inline(data)
                    log.info(f"[SKILL] write_skill result: {result}")
                    results.append(result)
                    continue

                # ── normal registered skills ─────────────────────────────
                if action in self.skill_manager.skills:
                    log.info(f"[SKILL] Executing: {action} with {data}")
                    result = self.skill_manager.run_skill(action, data)
                    log.info(f"[SKILL] Result: {result}")
                    results.append(result)

            except (json.JSONDecodeError, KeyError):
                pass
        return results

    def chat(self, user_input):
        full_response = ""
        for chunk in self.chat_stream(user_input):
            full_response += chunk
        return full_response

if __name__ == "__main__":
    # Quick test
    mem = MemorySystem()
    mello_chat = MelloChat(mem)
    print("Mello Chat initialized. Type 'exit' to quit.")
    while True:
        user_msg = input("You: ")
        if user_msg.lower() in ['exit', 'quit']:
            break
        print(f"Mello: {mello_chat.chat(user_msg)}")
