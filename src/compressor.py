import ollama
import json
from .memory import MemorySystem

class MemoryCompressor:
    def __init__(self, memory: MemorySystem, model="qwen3.5:4b"):
        self.memory = memory
        self.model = model

    def compress_recent_events(self, limit=10):
        """Summarizes events and extracts user preferences"""
        events = self.memory.query_episodic_memory(limit=limit)
        if not events or len(events) < 5:
            return None
            
        event_descriptions = [f"- {e[3]}" for e in events]
        events_text = "\n".join(event_descriptions)
        
        prompt = f"""
        Analyze these recent desktop events and provide two things:
        1. A one-sentence summary of the activity.
        2. Any user preferences or patterns you detect (e.g., naming style, folder choice).
        
        Respond in JSON format:
        {{
            "summary": "...",
            "preferences": {{ "key": "value" }}
        }}
        
        Events:
        {events_text}
        """
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            content = response['response'].strip()
            
            # Simple cleanup for JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                summary = data.get("summary")
                preferences = data.get("preferences", {})
                
                # Save summary to episodic memory
                self.memory.add_episodic_memory(
                    event_type="memory_summary",
                    description=f"Pattern: {summary}",
                    metadata={"compressed_count": len(events)}
                )
                
                # Save preferences to semantic memory
                for key, val in preferences.items():
                    print(f"[Preference Learned: {key} = {val}]")
                    self.memory.update_semantic_memory(key, val)
                
                return summary
            return None
        except Exception as e:
            print(f"Compression error: {e}")
            return None

if __name__ == "__main__":
    # Test Compressor
    mem = MemorySystem()
    compressor = MemoryCompressor(mem)
    print("Compressing events...")
    print(compressor.compress_recent_events())
