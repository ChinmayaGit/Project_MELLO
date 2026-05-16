import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .memory import MemorySystem
from .classifier import Classifier

class MelloEventHandler(FileSystemEventHandler):
    def __init__(self, memory, classifier):
        self.memory = memory
        self.classifier = classifier

    def process_file(self, file_path):
        if os.path.isdir(file_path):
            return
            
        filename = os.path.basename(file_path)
        print(f"Processing file: {filename}")
        
        # 1. Classify file
        classification = self.classifier.classify_file(filename)
        print(f"Classification for {filename}: {classification.get('category', 'Unknown')}")
        
        # 2. Record in memory
        self.memory.add_episodic_memory(
            event_type="file_detected",
            description=f"File detected: {filename}",
            metadata={
                "path": file_path,
                "classification": classification
            }
        )
        print(f"Recorded {filename} in episodic memory.")

    def on_created(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.process_file(event.dest_path)

def scan_existing_files(path_to_watch, memory, classifier):
    print(f"Scanning existing files in {path_to_watch}...")
    for filename in os.listdir(path_to_watch):
        file_path = os.path.join(path_to_watch, filename)
        if os.path.isfile(file_path):
            # Check if we already have this in memory to avoid duplicates
            # (Simple check: is it in the last 100 events?)
            # For now, let's just process it.
            MelloEventHandler(memory, classifier).process_file(file_path)

def start_watching(path_to_watch, memory, classifier):
    # Scan existing first
    scan_existing_files(path_to_watch, memory, classifier)
    
    event_handler = MelloEventHandler(memory, classifier)
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=False)
    observer.start()
    print(f"Watching folder: {path_to_watch}")
    return observer

if __name__ == "__main__":
    # Example usage (will need a proper entry point)
    mem = MemorySystem()
    clf = Classifier()
    watch_path = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.exists(watch_path):
        os.makedirs("test_watch", exist_ok=True)
        watch_path = "test_watch"
    
    start_watching(watch_path, mem, clf)
