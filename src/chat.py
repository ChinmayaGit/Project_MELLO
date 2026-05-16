import ollama
import json
from .memory import MemorySystem
from .skills import SkillManager

class MelloChat:
    def __init__(self, memory: MemorySystem, model="qwen3.5:4b", think_enabled=True):
        self.memory = memory
        self.model = model
        self.think_enabled = think_enabled
        self.skill_manager = SkillManager()
        self.messages = [
            {"role": "system", "content": f"""
            You are Mello, a local-first AI assistant. 
            {"Respond directly and concisely. Do NOT show <think> tags." if not self.think_enabled else ""}
            
            {self.skill_manager.get_skill_manifest()}
            
            To use a skill, include a JSON block:
            {{ "action": "skill_name", "path": "..." }}
            """}
        ]

    def get_context(self, user_query=None):
        # 1. Get recent context (Short-term memory)
        recent_events = self.memory.query_episodic_memory(limit=3)
        context_str = "Recent Events:\n"
        for event in recent_events:
            context_str += f"- {event[3]}\n"
        
        # 2. Get semantically relevant context (Long-term/Semantic retrieval)
        if user_query:
            semantic_results = self.memory.semantic_search(user_query, limit=3)
            if semantic_results and semantic_results['documents']:
                context_str += "\nRelevant Past Memories:\n"
                for doc in semantic_results['documents'][0]:
                    if doc not in context_str: # Avoid duplication
                        context_str += f"- {doc}\n"
        
        return context_str

    def chat_stream(self, user_input):
        # Refresh the system prompt every time to ensure the skill manifest is up to date
        self.messages[0]["content"] = f"""
            You are Mello, a local-first AI assistant. 
            {"Respond directly and concisely. Do NOT show <think> tags." if not self.think_enabled else ""}
            
            {self.skill_manager.get_skill_manifest()}
            
            GUIDELINES:
            1. Use 'mkdir' skill for creating folders (don't use run_command).
            2. For 'screenshot', do not provide a path parameter, just {{ "action": "screenshot" }}.
            3. Always confirm actions to the user.
            
            To use a skill, include a JSON block:
            {{ "action": "skill_name", "param": "..." }}
        """
        
        # Perform semantic retrieval based on the input
        context = self.get_context(user_input)
        
        user_message = {"role": "user", "content": f"Context: {context}\n\nUser: {user_input}"}
        self.messages.append(user_message)
        
        # Limit history to last 5 turns for max speed
        if len(self.messages) > 11:
            self.messages = [self.messages[0]] + self.messages[-10:]

        try:
            stream = ollama.chat(model=self.model, messages=self.messages, stream=True)
            full_response = ""
            in_think_block = False
            
            for chunk in stream:
                text = chunk['message']['content']
                full_response += text
                
                if not self.think_enabled:
                    if "<think>" in text:
                        in_think_block = True
                        yield " (thinking...)"
                        continue
                    if "</think>" in text:
                        in_think_block = False
                        continue
                    
                    if not in_think_block:
                        yield text
                    else:
                        # Optional: yield a tiny dot to show progress during thinking
                        yield "."
                else:
                    yield text
            
            self.messages.append({"role": "assistant", "content": full_response})
        except Exception as e:
            yield f"Error: {str(e)}"

    def chat(self, user_input):
        # Kept for backward compatibility if needed
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
