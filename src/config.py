import os
from pathlib import Path
from dotenv import load_dotenv

# Try to load .env file if it exists
load_dotenv()

# Path setup
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.getenv("CACHE_DIR", str(BASE_DIR / "cache"))

# Logseq configuration
# Default to a sample path, user should update this
LOGSEQ_NOTES_DIR = os.getenv("LOGSEQ_NOTES_DIR", "D:\logseq\journals")

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral:latest")

# Database configuration
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vectordb")

# Model cache configuration
SENTENCE_TRANSFORMERS_HOME = os.getenv("SENTENCE_TRANSFORMERS_HOME", os.path.join(CACHE_DIR, "sentence_transformers"))
TRANSFORMERS_CACHE = os.getenv("TRANSFORMERS_CACHE", os.path.join(CACHE_DIR, "transformers"))
TORCH_HOME = os.getenv("TORCH_HOME", os.path.join(CACHE_DIR, "torch"))

# App configuration
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", 8501))

# Create necessary directories
def create_directories():
    # Create data directories
    Path(VECTOR_DB_PATH).mkdir(parents=True, exist_ok=True)
    Path("./data/processed").mkdir(parents=True, exist_ok=True)
    Path("./logs").mkdir(parents=True, exist_ok=True)
    
    # Create cache directories
    Path(SENTENCE_TRANSFORMERS_HOME).mkdir(parents=True, exist_ok=True)
    Path(TRANSFORMERS_CACHE).mkdir(parents=True, exist_ok=True)
    Path(TORCH_HOME).mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for cache locations
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = SENTENCE_TRANSFORMERS_HOME
    os.environ["TRANSFORMERS_CACHE"] = TRANSFORMERS_CACHE
    os.environ["TORCH_HOME"] = TORCH_HOME

if __name__ == "__main__":
    create_directories()
    print("Configuration loaded and directories created.") 