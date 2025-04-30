import os
import json
import requests
import logging
from typing import Dict, List, Optional, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", default_model="mistral:latest"):
        """
        Initialize the Ollama client
        
        Args:
            base_url (str): Base URL for Ollama API
            default_model (str): Default model to use
        """
        self.base_url = base_url
        self.default_model = default_model
        self.api_url = f"{base_url}/api"
        logger.info(f"Initialized OllamaClient with base URL: {base_url}, default model: {default_model}")
    
    def list_models(self) -> List[str]:
        """List all available models"""
        try:
            response = requests.get(f"{self.api_url}/tags")
            if response.status_code == 200:
                models = response.json()
                return [model["name"] for model in models["models"]]
            else:
                logger.error(f"Failed to list models: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    def generate(self, 
                prompt: str, 
                model: Optional[str] = None, 
                system_prompt: Optional[str] = None,
                temperature: float = 0.7,
                max_tokens: int = 2048,
                stream: bool = False) -> Dict[str, Any]:
        """
        Generate text from a prompt
        
        Args:
            prompt (str): The prompt to generate from
            model (str, optional): Model to use, defaults to the default model
            system_prompt (str, optional): System prompt to use
            temperature (float): Temperature for generation
            max_tokens (int): Maximum tokens to generate
            stream (bool): Whether to stream the response
            
        Returns:
            dict: The generated response
        """
        model = model or self.default_model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            endpoint = f"{self.api_url}/generate"
            
            if stream:
                # Streaming implementation
                logger.info(f"Streaming response from model {model}")
                response = requests.post(endpoint, json=payload, stream=True)
                
                if response.status_code != 200:
                    logger.error(f"Failed to generate: {response.text}")
                    return {"error": response.text}
                
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response += chunk["response"]
                            yield chunk
                
                return {"response": full_response, "model": model}
            else:
                # Non-streaming implementation
                logger.info(f"Generating response from model {model}")
                response = requests.post(endpoint, json=payload)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to generate: Status {response.status_code}, Response: {response.text}")
                    return {"error": f"API Error {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error generating from model: {e}")
            return {"error": str(e)}
    
    def process_note(self, note_content: str, task_type: str = "enhance") -> Dict[str, Any]:
        """Process a note using the LLM"""
        try:
            # Create a simple prompt based on task type
            if task_type == "enhance":
                prompt = f"Please enhance this note by improving clarity and organization:\n\n{note_content}"
            elif task_type == "summarize":
                prompt = f"Please summarize this note:\n\n{note_content}"
            elif task_type == "tag":
                prompt = f"Extract key tags from this note as a comma-separated list:\n\n{note_content}"
            else:
                prompt = f"Please enhance this note:\n\n{note_content}"
            
            # Make direct API call similar to our test script
            payload = {
                "model": "mistral:latest",  # Hardcoded to the model we know works
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(f"{self.api_url}/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Ollama API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Error: {str(e)}"}

if __name__ == "__main__":
    # Example usage
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import OLLAMA_BASE_URL, DEFAULT_MODEL
    
    client = OllamaClient(OLLAMA_BASE_URL, DEFAULT_MODEL)
    
    # List models
    models = client.list_models()
    print(f"Available models: {models}")
    
    # Generate a simple response
    response = client.generate("What is a second brain?")
    print(f"Response: {response.get('response', 'No response')}") 