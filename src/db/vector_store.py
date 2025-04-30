import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, persist_directory):
        """
        Initialize the vector store
        
        Args:
            persist_directory (str): Directory to persist the database
        """
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # Use the default embedding function from ChromaDB
        # In production, you might want to use a more robust one like OpenAI's
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction()
        
        # Create collections for different types of content
        self.notes_collection = self.client.get_or_create_collection(
            name="notes",
            embedding_function=self.embedding_function
        )
        
        self.journals_collection = self.client.get_or_create_collection(
            name="journals",
            embedding_function=self.embedding_function
        )
        
        logger.info(f"Initialized VectorStore with persist directory: {persist_directory}")
    
    def add_note(self, note_data: Dict[str, Any]):
        """
        Add a note to the vector store
        
        Args:
            note_data (dict): Note data to add
        """
        try:
            # Extract required fields
            note_id = note_data.get('path', '').replace('\\', '_').replace('/', '_')
            if not note_id:
                note_id = f"note_{len(self.notes_collection.get()['ids'])}"
            
            content = note_data.get('clean_content', '')
            if not content:
                logger.warning(f"Empty content for note: {note_id}")
                return
            
            # Prepare metadata
            metadata = {
                "title": note_data.get('title', ''),
                "path": note_data.get('path', ''),
                "is_journal": note_data.get('is_journal', False),
                "tags": ",".join(note_data.get('tags', [])),
                "journal_date": note_data.get('journal_date', ''),
                "last_modified": note_data.get('last_modified', '')
            }
            
            # Choose the appropriate collection
            collection = self.journals_collection if metadata["is_journal"] else self.notes_collection
            
            # Add to collection
            collection.upsert(
                ids=[note_id],
                documents=[content],
                metadatas=[metadata]
            )
            
            logger.info(f"Added note to vector store: {note_id}")
            return note_id
        except Exception as e:
            logger.error(f"Error adding note to vector store: {e}")
            return None
    
    def add_notes_batch(self, notes_data: List[Dict[str, Any]]):
        """
        Add multiple notes to the vector store in batch
        
        Args:
            notes_data (list): List of note data to add
        """
        regular_notes = []
        journal_notes = []
        
        for note in notes_data:
            if note.get('is_journal', False):
                journal_notes.append(note)
            else:
                regular_notes.append(note)
        
        # Process regular notes
        if regular_notes:
            ids = []
            documents = []
            metadatas = []
            
            for note in regular_notes:
                note_id = note.get('path', '').replace('\\', '_').replace('/', '_')
                if not note_id:
                    note_id = f"note_{len(ids)}"
                
                content = note.get('clean_content', '')
                if not content:
                    logger.warning(f"Empty content for note: {note_id}")
                    continue
                
                metadata = {
                    "title": note.get('title', ''),
                    "path": note.get('path', ''),
                    "is_journal": False,
                    "tags": ",".join(note.get('tags', [])),
                    "last_modified": note.get('last_modified', '')
                }
                
                ids.append(note_id)
                documents.append(content)
                metadatas.append(metadata)
            
            if ids:
                self.notes_collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                logger.info(f"Added {len(ids)} regular notes to vector store")
        
        # Process journal notes
        if journal_notes:
            ids = []
            documents = []
            metadatas = []
            
            for note in journal_notes:
                note_id = note.get('path', '').replace('\\', '_').replace('/', '_')
                if not note_id:
                    note_id = f"journal_{len(ids)}"
                
                content = note.get('clean_content', '')
                if not content:
                    logger.warning(f"Empty content for journal: {note_id}")
                    continue
                
                metadata = {
                    "title": note.get('title', ''),
                    "path": note.get('path', ''),
                    "is_journal": True,
                    "journal_date": note.get('journal_date', ''),
                    "tags": ",".join(note.get('tags', [])),
                    "last_modified": note.get('last_modified', '')
                }
                
                ids.append(note_id)
                documents.append(content)
                metadatas.append(metadata)
            
            if ids:
                self.journals_collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                logger.info(f"Added {len(ids)} journal notes to vector store")
    
    def search(self, 
              query: str, 
              collection_name: str = "all", 
              filter_criteria: Optional[Dict[str, Any]] = None,
              limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search the vector store
        
        Args:
            query (str): Query to search for
            collection_name (str): Collection to search in ('all', 'notes', 'journals')
            filter_criteria (dict, optional): Filter criteria for search
            limit (int): Maximum number of results to return
            
        Returns:
            list: Search results
        """
        results = []
        
        try:
            collections = []
            if collection_name == "all" or collection_name == "notes":
                collections.append(self.notes_collection)
            if collection_name == "all" or collection_name == "journals":
                collections.append(self.journals_collection)
            
            for collection in collections:
                collection_results = collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=filter_criteria
                )
                
                for i, doc_id in enumerate(collection_results['ids'][0]):
                    result = {
                        'id': doc_id,
                        'content': collection_results['documents'][0][i],
                        'metadata': collection_results['metadatas'][0][i],
                        'distance': collection_results['distances'][0][i] if 'distances' in collection_results else None
                    }
                    results.append(result)
            
            # Sort by distance (if available)
            if results and results[0]['distance'] is not None:
                results.sort(key=lambda x: x['distance'])
            
            # Limit the final results
            results = results[:limit]
            
            logger.info(f"Found {len(results)} results for query: {query}")
            return results
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def search_by_date(self, date_str: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search journal entries by date
        
        Args:
            date_str (str): Date string in format YYYY-MM-DD
            limit (int): Maximum number of results to return
            
        Returns:
            list: Search results
        """
        try:
            filter_criteria = {"journal_date": date_str}
            
            results = self.journals_collection.get(
                where=filter_criteria,
                limit=limit
            )
            
            formatted_results = []
            for i, doc_id in enumerate(results['ids']):
                result = {
                    'id': doc_id,
                    'content': results['documents'][i],
                    'metadata': results['metadatas'][i]
                }
                formatted_results.append(result)
            
            logger.info(f"Found {len(formatted_results)} journal entries for date: {date_str}")
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching journals by date: {e}")
            return []
    
    def search_by_tag(self, tag: str, collection_name: str = "all", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search notes by tag
        
        Args:
            tag (str): Tag to search for
            collection_name (str): Collection to search in ('all', 'notes', 'journals')
            limit (int): Maximum number of results to return
            
        Returns:
            list: Search results
        """
        try:
            results = []
            collections = []
            
            if collection_name == "all" or collection_name == "notes":
                collections.append(self.notes_collection)
            if collection_name == "all" or collection_name == "journals":
                collections.append(self.journals_collection)
            
            for collection in collections:
                collection_results = collection.get(
                    where={"tags": {"$contains": tag}},
                    limit=limit
                )
                
                for i, doc_id in enumerate(collection_results['ids']):
                    result = {
                        'id': doc_id,
                        'content': collection_results['documents'][i],
                        'metadata': collection_results['metadatas'][i]
                    }
                    results.append(result)
            
            # Limit the final results
            results = results[:limit]
            
            logger.info(f"Found {len(results)} results for tag: {tag}")
            return results
        except Exception as e:
            logger.error(f"Error searching by tag: {e}")
            return []

if __name__ == "__main__":
    # Example usage
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import VECTOR_DB_PATH
    
    vector_store = VectorStore(VECTOR_DB_PATH)
    
    # Test adding a single note
    test_note = {
        'title': 'Test Note',
        'path': 'test/note.md',
        'content': 'This is a test note with #tag1 and #tag2',
        'clean_content': 'This is a test note with tag1 and tag2',
        'metadata': {},
        'is_journal': False,
        'tags': ['tag1', 'tag2'],
        'last_modified': '2023-01-01T12:00:00'
    }
    
    note_id = vector_store.add_note(test_note)
    print(f"Added note with ID: {note_id}")
    
    # Test search
    search_results = vector_store.search("test note")
    print(f"Search results: {search_results}") 