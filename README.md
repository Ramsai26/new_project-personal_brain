# Personal Brain

A second brain application that processes and enhances your Logseq notes using local LLMs through Ollama.

## Features

- Process and index Logseq journal entries and pages
- Search your notes using natural language
- Enhance rough notes with AI assistance
- Extract tags and summaries from your content
- All processing happens locally using Ollama

## Requirements

- Python 3.8+
- Ollama with at least one model installed (recommended: mistral:latest)
- Logseq with notes/journals

## Installation

1. Clone this repository:
```
git clone https://github.com/yourusername/personal-brain.git
cd personal-brain
```

2. Create a virtual environment and install dependencies:
```
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux/Mac
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Configure your Logseq directory in `src/config.py` or using environment variables.

## Usage

1. Make sure Ollama is running with at least one model installed:
```
ollama run mistral:latest
```

2. Process your notes:
```
python main.py --process
```

3. Start the web server:
```
python main.py --serve
```

4. Access the web interface at http://localhost:5000

## Configuration

You can configure the application by:
- Editing `src/config.py`
- Creating a `.env` file in the root directory
- Setting environment variables

Key configuration options:
- `LOGSEQ_NOTES_DIR`: Path to your Logseq notes
- `DEFAULT_MODEL`: Ollama model to use (default: mistral:latest)
- `FLASK_PORT`: Port for the web server

## License

MIT

## Acknowledgements

- [Logseq](https://logseq.com/)
- [Ollama](https://github.com/ollama/ollama)
- [LlamaIndex](https://github.com/jerryjliu/llama_index)
- [LangChain](https://github.com/langchain-ai/langchain)
- [ChromaDB](https://github.com/chroma-core/chroma)
- [Sentence-Transformers](https://github.com/UKPLab/sentence-transformers) 