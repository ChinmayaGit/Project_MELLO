import os
import ollama
import json
import re
import time
import logging
from .memory import MemorySystem
from .skills import SkillManager

log = logging.getLogger("mello.chat")

class MelloChat:
    def __init__(self, memory: MemorySystem, model="qwen3.5:4b", think_enabled=True, watch_path="./test_watch"):
        self.memory = memory
        self.model = model
        self.think_enabled = think_enabled
        self.watch_path = os.path.abspath(watch_path)
        self.skill_manager = SkillManager()
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

{self.skill_manager.get_skill_manifest()}

RULES:
1. To use a skill, output a JSON block on its own line, e.g.:
   {{"action": "mkdir", "path": "{self.watch_path}\\my_folder"}}
2. Use mkdir for folders, create_file for files.
3. Always use absolute paths.
4. After the JSON block, confirm what you did in plain text."""
        if self.messages:
            self.messages[0]["content"] = system
        else:
            self.messages = [{"role": "system", "content": system}]

    def get_context(self, user_query=None):
        t0 = time.perf_counter()

        # 1. Get recent context (Short-term memory)
        recent_events = self.memory.query_episodic_memory(limit=3)
        context_str = "Recent Events:\n"
        for event in recent_events:
            context_str += f"- {event[3]}\n"
        t1 = time.perf_counter()
        log.info(f"[PERF] SQLite episodic query: {(t1-t0)*1000:.1f}ms")

        # 2. Get semantically relevant context (Long-term/Semantic retrieval)
        if user_query:
            semantic_results = self.memory.semantic_search(user_query, limit=3)
            t2 = time.perf_counter()
            log.info(f"[PERF] ChromaDB semantic search: {(t2-t1)*1000:.1f}ms")
            if semantic_results and semantic_results['documents']:
                context_str += "\nRelevant Past Memories:\n"
                for doc in semantic_results['documents'][0]:
                    if doc not in context_str:
                        context_str += f"- {doc}\n"

        log.info(f"[PERF] get_context total: {(time.perf_counter()-t0)*1000:.1f}ms")
        return context_str

    def chat_stream(self, user_input):
        self._build_system_prompt()
        
        t_start = time.perf_counter()

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
                self.memory.add_episodic_memory("skill_execution", result)
                yield f"\n\n**[Done]** {result}"

        except Exception as e:
            log.error(f"[PERF] ollama.chat error: {e}")
            yield f"Error: {str(e)}"

    def _execute_skills(self, response_text):
        """Parse LLM response for skill JSON blocks and execute them."""
        results = []
        seen = set()
        for match in re.finditer(r'\{[^{}]+\}', response_text, re.DOTALL):
            json_str = match.group().strip()
            if json_str in seen:
                continue
            seen.add(json_str)
            try:
                data = json.loads(json_str)
                action = data.get("action")
                if action and action in self.skill_manager.skills:
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
