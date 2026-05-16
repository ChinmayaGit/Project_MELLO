import chromadb
from chromadb.utils import embedding_functions
import os

class VectorMemory:
    def __init__(self, persist_directory="mello_vector_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        # Using a default embedding function (sentence-transformers)
        # Note: In a real local-first app, we'd use a local ONNX model or Ollama embeddings
        self.collection = self.client.get_or_create_collection(
            name="mello_events",
            metadata={"hnsw:space": "cosine"}
        )

    def add_event(self, event_id, text, metadata):
        """Adds an event to the vector database for semantic search"""
        self.collection.add(
            ids=[str(event_id)],
            documents=[text],
            metadatas=[metadata]
        )

    def search(self, query, n_results=5):
        """Searches for semantically similar events"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

if __name__ == "__main__":
    # Test Vector Memory
    vm = VectorMemory("test_vector_db")
    vm.add_event(1, "User added a new invoice for Amazon in May 2026", {"type": "file_event"})
    vm.add_event(2, "Mello organized the movies folder", {"type": "skill_event"})
    
    print("Search results for 'purchases':")
    print(vm.search("purchases"))
