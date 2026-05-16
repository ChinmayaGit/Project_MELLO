import ollama
import json

class Classifier:
    def __init__(self, model="qwen3.5:0.8b"):
        self.model = model

    def classify_file(self, filename):
        prompt = f"""
        Classify this file into ONE category: [Document, Image, Video, Audio, Code, Compressed, Other]
        File: {filename}
        Output format: {{"category": "NAME", "confidence": 0.9}}
        """
        
        try:
            # Use a shorter timeout or limit tokens if possible
            response = ollama.generate(model=self.model, prompt=prompt, options={"num_predict": 50})
            content = response['response'].strip()
            
            # Extract JSON from potential markdown or text
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            
            return json.loads(content)
        except Exception as e:
            return {"category": "Other", "confidence": 0.0, "error": str(e)}

if __name__ == "__main__":
    # Test Classifier
    classifier = Classifier()
    print("Classifying 'invoice.pdf':", classifier.classify_file("invoice.pdf"))
    print("Classifying 'vacation.jpg':", classifier.classify_file("vacation.jpg"))
    print("Classifying 'main.py':", classifier.classify_file("main.py"))
