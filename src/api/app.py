import sys
import os
import json
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_processor import BrainProcessor
from config import FLASK_PORT, LOGSEQ_NOTES_DIR, VECTOR_DB_PATH, DEFAULT_MODEL, create_directories

# Create necessary directories
create_directories()

# Initialize Flask app
app = Flask(__name__, 
            template_folder='../../templates',
            static_folder='../../static')
CORS(app)  # Enable CORS for all routes

# Initialize the brain processor
brain = BrainProcessor(
    logseq_dir=LOGSEQ_NOTES_DIR,
    vector_db_path=VECTOR_DB_PATH,
    model=DEFAULT_MODEL
)

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """Get the status of the brain processor"""
    return jsonify({
        "is_ready": brain.is_ready(),
        "components": {
            "parser": brain.parser is not None,
            "llm": brain.llm is not None,
            "vector_store": brain.vector_store is not None
        }
    })

@app.route('/api/process', methods=['POST'])
def process_notes():
    """Process all notes from Logseq"""
    stats = brain.process_all_notes()
    return jsonify(stats)

@app.route('/api/search', methods=['GET', 'POST'])
def search():
    """Search the brain"""
    if request.method == 'POST':
        data = request.json
        query = data.get('query', '')
        collection = data.get('collection', 'all')
        limit = int(data.get('limit', 5))
    else:
        query = request.args.get('query', '')
        collection = request.args.get('collection', 'all')
        limit = int(request.args.get('limit', 5))
    
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    results = brain.search_brain(query, collection=collection, limit=limit)
    return jsonify(results)

@app.route('/api/search/date', methods=['GET', 'POST'])
def search_date():
    """Search journal entries by date"""
    if request.method == 'POST':
        data = request.json
        date_str = data.get('date', '')
        limit = int(data.get('limit', 5))
    else:
        date_str = request.args.get('date', '')
        limit = int(request.args.get('limit', 5))
    
    if not date_str:
        return jsonify({"error": "Date is required"}), 400
    
    results = brain.search_by_date(date_str, limit=limit)
    return jsonify(results)

@app.route('/api/enhance', methods=['POST'])
def enhance_note():
    """Enhance a note using the LLM"""
    app.logger.info("Received request for /api/enhance")
    try:
        data = request.json
        if not data:
            app.logger.warning("Invalid JSON payload received")
            return jsonify({"error": "Invalid JSON payload"}), 400
            
        content = data.get('content', '')
        task = data.get('task', 'enhance')
        
        if not content:
            app.logger.warning("Content is required but not provided")
            return jsonify({"error": "Content is required"}), 400
        
        app.logger.info(f"Enhancing note with task: {task}, content length: {len(content)}")
        
        # Check if the brain is ready
        if not brain.is_ready():
            app.logger.error("Brain not ready for enhance_note request")
            return jsonify({"error": "Brain is not ready. Make sure all services are running."}), 503
        
        app.logger.info("Calling brain.enhance_note...")
        result = brain.enhance_note(content, task=task)
        app.logger.info(f"Received result from brain.enhance_note: {result}")
        
        if result and 'error' in result:
            app.logger.error(f"Error enhancing note reported by brain: {result['error']}")
            # Ensure we return a 500 if brain.enhance_note signals an error
            return jsonify(result), 500 
            
        # Ensure result is not None before returning
        if result is None:
            app.logger.error("brain.enhance_note returned None")
            return jsonify({"error": "Internal server error: No response from brain processing."}), 500

        app.logger.info("Successfully processed enhance request, returning result.")
        return jsonify(result)
        
    except Exception as e:
        # Log the full exception traceback
        app.logger.error(f"Exception in enhance_note route: {str(e)}", exc_info=True) 
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/models', methods=['GET'])
def list_models():
    """List available LLM models"""
    if brain.llm:
        models = brain.llm.list_models()
        return jsonify(models)
    return jsonify({"error": "LLM is not initialized"}), 500

@app.route('/api/notes/stats', methods=['GET'])
def notes_stats():
    """Get statistics about processed notes"""
    try:
        stats_files = list(Path('./data/processed').glob('processing_stats_*.json'))
        
        if not stats_files:
            return jsonify({"message": "No processing stats available yet"}), 200
        
        # Get the most recent stats file
        latest_stats_file = max(stats_files, key=lambda p: p.stat().st_mtime)
        
        with open(latest_stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not brain.is_ready():
        print("Warning: BrainProcessor is not fully initialized. Some features may not work.")
    
    print(f"Starting Personal Brain API on port {FLASK_PORT}")
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=True) 