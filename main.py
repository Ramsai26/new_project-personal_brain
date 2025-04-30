import os
import sys
import argparse
from pathlib import Path

# Add the src directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.append(src_dir)

from config import create_directories, FLASK_PORT, LOGSEQ_NOTES_DIR
from brain_processor import BrainProcessor

def setup_argparse():
    """Set up command line arguments"""
    parser = argparse.ArgumentParser(description="Personal Brain - Your Second Brain with Local LLM Integration")
    
    parser.add_argument('--process', action='store_true', help='Process and index all Logseq notes')
    parser.add_argument('--serve', action='store_true', help='Start the web server')
    parser.add_argument('--logseq-dir', type=str, help='Path to Logseq notes directory')
    parser.add_argument('--port', type=int, default=FLASK_PORT, help='Port for the web server')
    
    return parser.parse_args()

def process_notes(logseq_dir=None):
    """Process all notes"""
    print("Processing notes...")
    
    # Initialize brain processor
    brain = BrainProcessor(logseq_dir=logseq_dir or LOGSEQ_NOTES_DIR)
    
    if not brain.is_ready():
        print("Error: Brain Processor is not ready. Check your configuration.")
        sys.exit(1)
    
    # Process all notes
    stats = brain.process_all_notes()
    
    if stats.get('status') == 'completed':
        print(f"Processing complete! Processed {stats.get('pages_processed', 0)} pages and {stats.get('journals_processed', 0)} journals.")
        return True
    else:
        print(f"Processing failed: {stats.get('error', 'Unknown error')}")
        return False

def start_server(port=None):
    """Start the web server"""
    print(f"Starting web server on port {port or FLASK_PORT}...")
    
    # Import the Flask app
    from api.app import app
    
    # Start the server
    app.run(host='0.0.0.0', port=port or FLASK_PORT, debug=True)

def main():
    """Main function"""
    # Create necessary directories
    create_directories()
    
    # Parse command line arguments
    args = setup_argparse()
    
    # If no arguments provided, show help
    if not (args.process or args.serve):
        print("No action specified. Use --process to process notes or --serve to start the web server.")
        print("Run 'python main.py --help' for more information.")
        return
    
    # Process notes if requested
    if args.process:
        success = process_notes(args.logseq_dir)
        if not success and not args.serve:
            return
    
    # Start the web server if requested
    if args.serve:
        start_server(args.port)

if __name__ == "__main__":
    main() 