import requests
import ollama

def test_ollama_connection():
    """Test direct connection to Ollama server"""
    print("Testing connection to Ollama server...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json()
            print("✅ Successfully connected to Ollama")
            print(f"Available models: {[model['name'] for model in models['models']]}")
            return True
        else:
            print(f"❌ Ollama server responded with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Ollama: {str(e)}")
        return False

def test_ollama_generation():
    """Test generating text with Ollama"""
    print("\nTesting text generation with Ollama...")
    try:
        payload = {
            "model": "mistral:latest",
            "prompt": "Hello, how are you today?",
            "stream": False
        }
        
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Successfully generated text:")
            print(result.get("response", "No response"))
            return True
        else:
            print(f"❌ Ollama generation failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error during generation: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== OLLAMA DIRECT CONNECTION TEST ===")
    if test_ollama_connection():
        test_ollama_generation()
    print("=== TEST COMPLETE ===")