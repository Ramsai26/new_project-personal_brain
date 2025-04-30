import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from utils.logseq_parser import LogseqParser
from llm.ollama_client import OllamaClient
from db.vector_store import VectorStore
from config import LOGSEQ_NOTES_DIR, VECTOR_DB_PATH, DEFAULT_MODEL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BrainProcessor:
    def __init__(self, 
                logseq_dir: str = LOGSEQ_NOTES_DIR, 
                vector_db_path: str = VECTOR_DB_PATH,
                model: str = DEFAULT_MODEL):
        """
        Initialize the brain processor
        
        Args:
            logseq_dir (str): Path to Logseq notes directory
            vector_db_path (str): Path to vector DB storage
            model (str): Default LLM model to use
        """
        self.logseq_dir = logseq_dir
        self.vector_db_path = vector_db_path
        self.model = model
        
        # Initialize components
        try:
            self.parser = LogseqParser(logseq_dir)
            logger.info(f"LogseqParser initialized with directory: {logseq_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize LogseqParser: {e}")
            self.parser = None
        
        try:
            self.llm = OllamaClient(default_model=model)
            logger.info(f"OllamaClient initialized with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize OllamaClient: {e}")
            self.llm = None
        
        try:
            self.vector_store = VectorStore(vector_db_path)
            logger.info(f"VectorStore initialized with path: {vector_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            self.vector_store = None
        
        # Create data directory if it doesn't exist
        self.processed_dir = Path("./data/processed")
        self.processed_dir.mkdir(parents=True, exist_ok=True)
    
    def is_ready(self) -> bool:
        """Check if all components are initialized properly"""
        return self.parser is not None and self.llm is not None and self.vector_store is not None
    
    def process_all_notes(self) -> Dict[str, Any]:
        """
        Process all notes from Logseq, enhance them with LLM, and store in vector DB
        
        Returns:
            dict: Processing statistics
        """
        if not self.is_ready():
            logger.error("BrainProcessor is not ready. Check component initialization.")
            return {"error": "BrainProcessor is not ready", "status": "failed"}
        
        start_time = datetime.now()
        stats = {
            "start_time": start_time.isoformat(),
            "pages_processed": 0,
            "journals_processed": 0,
            "enhanced_count": 0,
            "errors": 0,
            "status": "in_progress"
        }
        
        try:
            # Export notes to JSON first
            export_path = self.processed_dir / "logseq_export.json"
            self.parser.export_to_json(export_path)
            
            # Load the exported data
            with open(export_path, 'r', encoding='utf-8') as f:
                all_notes = json.load(f)
            
            # Process and enhance pages
            for page in all_notes.get('pages', []):
                try:
                    # Enhance page content with LLM if content is not too long
                    content = page.get('content', '')
                    if content and len(content) < 4000:  # Limit to avoid token limits
                        enhancement = self.llm.process_note(content, task_type="enhance")
                        if enhancement and 'response' in enhancement:
                            page['enhanced_content'] = enhancement['response']
                            page['clean_content'] = enhancement['response']
                            stats["enhanced_count"] += 1
                    
                    # Add to vector store
                    self.vector_store.add_note(page)
                    stats["pages_processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing page {page.get('title', 'unknown')}: {e}")
                    stats["errors"] += 1
            
            # Process and enhance journals
            for journal in all_notes.get('journals', []):
                try:
                    # Add to vector store without enhancement (journals usually just need to be searchable)
                    self.vector_store.add_note(journal)
                    stats["journals_processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing journal {journal.get('title', 'unknown')}: {e}")
                    stats["errors"] += 1
            
            end_time = datetime.now()
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = (end_time - start_time).total_seconds()
            stats["status"] = "completed"
            
            # Save stats
            stats_path = self.processed_dir / f"processing_stats_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
            
            logger.info(f"Processed {stats['pages_processed']} pages and {stats['journals_processed']} journals")
            return stats
        
        except Exception as e:
            logger.error(f"Error in process_all_notes: {e}")
            stats["status"] = "failed"
            stats["error"] = str(e)
            return stats
    
    def search_brain(self, query: str, collection: str = "all", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search the brain using natural language
        
        Args:
            query (str): Natural language query
            collection (str): Collection to search in ('all', 'notes', 'journals')
            limit (int): Maximum number of results to return
            
        Returns:
            list: Search results
        """
        if not self.is_ready():
            logger.error("BrainProcessor is not ready for search")
            return [{"error": "BrainProcessor is not ready"}]
        
        try:
            # Search using vector store
            results = self.vector_store.search(query, collection_name=collection, limit=limit)
            
            # If we have results, use LLM to create a summary
            if results:
                # Prepare context from results
                context = "\n\n".join([
                    f"Document: {r['metadata'].get('title', 'Untitled')}\nContent: {r['content'][:500]}..."
                    for r in results
                ])
                
                # Create a prompt for the LLM
                prompt = (
                    f"I want to answer the question: '{query}'\n\n"
                    f"Here are the relevant documents:\n{context}\n\n"
                    f"Based on these documents, provide a comprehensive answer to the question."
                )
                
                # Get LLM response
                llm_response = self.llm.generate(prompt)
                
                if llm_response and 'response' in llm_response:
                    # Add the LLM summary to the results
                    summary = {
                        'id': 'summary',
                        'content': llm_response['response'],
                        'metadata': {
                            'title': f"Summary for query: {query}",
                            'is_summary': True
                        }
                    }
                    results.insert(0, summary)
            
            return results
        except Exception as e:
            logger.error(f"Error in search_brain: {e}")
            return [{"error": str(e)}]
    
    def search_by_date(self, date_str: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search journal entries by date
        
        Args:
            date_str (str): Date string in format YYYY-MM-DD
            limit (int): Maximum number of results to return
            
        Returns:
            list: Search results
        """
        if not self.is_ready():
            logger.error("BrainProcessor is not ready for date search")
            return [{"error": "BrainProcessor is not ready"}]
        
        try:
            # Search by date using vector store
            results = self.vector_store.search_by_date(date_str, limit=limit)
            
            # If we have results, use LLM to create a summary
            if results:
                # Prepare context from results
                context = "\n\n".join([
                    f"Journal Entry ({r['metadata'].get('journal_date', 'Unknown Date')}):\n{r['content'][:500]}..."
                    for r in results
                ])
                
                # Create a prompt for the LLM
                prompt = (
                    f"I want to summarize what I was thinking about on {date_str}.\n\n"
                    f"Here are the relevant journal entries:\n{context}\n\n"
                    f"Please provide a concise summary of the key thoughts, activities, and ideas from this day."
                )
                
                # Get LLM response
                llm_response = self.llm.generate(prompt)
                
                if llm_response and 'response' in llm_response:
                    # Add the LLM summary to the results
                    summary = {
                        'id': 'summary',
                        'content': llm_response['response'],
                        'metadata': {
                            'title': f"Summary for date: {date_str}",
                            'is_summary': True,
                            'journal_date': date_str
                        }
                    }
                    results.insert(0, summary)
            
            return results
        except Exception as e:
            logger.error(f"Error in search_by_date: {e}")
            return [{"error": str(e)}]
    
    def enhance_note(self, note_content: str, task: str = "enhance") -> Dict[str, Any]:
        """
        Enhance a note using the LLM
        
        Args:
            note_content (str): The note content to enhance
            task (str): The enhancement task (summarize, tag, enhance)
            
        Returns:
            dict: The enhanced note
        """
        logger.info(f"BrainProcessor: Enhancing note with task: {task}")
        
        if not self.llm:
            logger.error("BrainProcessor: LLM is not initialized for enhance_note")
            return {"error": "LLM is not initialized. Please make sure Ollama is running."}
        
        if not note_content or note_content.strip() == "":
            logger.warning("BrainProcessor: Empty note content provided")
            return {"error": "Note content cannot be empty"}
        
        # Validate task type
        valid_tasks = ["summarize", "tag", "enhance"]
        if task not in valid_tasks:
            logger.warning(f"BrainProcessor: Invalid task type: {task}, defaulting to enhance")
            task = "enhance"
        
        try:
            logger.info(f"BrainProcessor: Sending note to LLM (task: {task}) with length: {len(note_content)}")
            result = self.llm.process_note(note_content, task_type=task)
            logger.info(f"BrainProcessor: Received result from llm.process_note: {result}")
            
            # Check if the response is valid or contains an error from the LLM client
            if not result:
                logger.error("BrainProcessor: Received None result from llm.process_note")
                return {"error": "Failed to get response from LLM."}
            elif 'error' in result:
                logger.error(f"BrainProcessor: LLM client reported error: {result['error']}")
                # Pass the error up, don't create a new one here
                return result
            elif 'response' not in result:
                logger.error(f"BrainProcessor: Invalid response structure from LLM: {result}")
                return {"error": "Invalid response structure from LLM."}

            logger.info(f"BrainProcessor: Successfully enhanced note. Response length: {len(result.get('response', ''))}")
            return result
            
        except Exception as e:
            logger.error(f"BrainProcessor: Exception during enhance_note: {str(e)}", exc_info=True)
            return {"error": f"Error enhancing note: {str(e)}"}

if __name__ == "__main__":
    # Example usage
    processor = BrainProcessor()
    
    if processor.is_ready():
        # Process all notes
        stats = processor.process_all_notes()
        print(f"Processing stats: {stats}")
        
        # Test search
        results = processor.search_brain("second brain concept")
        print(f"\nSearch results for 'second brain concept':")
        for result in results:
            print(f"- {result.get('metadata', {}).get('title', 'Untitled')}: {result.get('content', '')[:100]}...")
    else:
        print("BrainProcessor is not ready. Check component initialization.") 