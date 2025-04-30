import os
import re
import json
from pathlib import Path
from datetime import datetime
import frontmatter
from bs4 import BeautifulSoup
import markdown
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LogseqParser:
    def __init__(self, notes_dir):
        """
        Initialize the Logseq parser
        
        Args:
            notes_dir (str): Path to the Logseq notes directory
        """
        self.notes_dir = Path(notes_dir)
        if not self.notes_dir.exists():
            raise FileNotFoundError(f"Notes directory not found: {notes_dir}")
        
        self.pages_dir = self.notes_dir / "pages"
        self.journals_dir = self.notes_dir / "journals"
        
        logger.info(f"Initialized LogseqParser with notes directory: {notes_dir}")
    
    def list_all_pages(self):
        """List all pages (non-journal notes)"""
        if not self.pages_dir.exists():
            logger.warning(f"Pages directory not found: {self.pages_dir}")
            return []
        
        return list(self.pages_dir.glob('*.md'))
    
    def list_all_journals(self):
        """List all journal entries"""
        if not self.journals_dir.exists():
            logger.warning(f"Journals directory not found: {self.journals_dir}")
            return []
        
        return list(self.journals_dir.glob('*.md'))
    
    def parse_file(self, file_path):
        """
        Parse a Logseq markdown file
        
        Args:
            file_path (Path): Path to the markdown file
            
        Returns:
            dict: Parsed content with metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter if exists
            try:
                post = frontmatter.loads(content)
                metadata = post.metadata
                content_text = post.content
            except:
                metadata = {}
                content_text = content
            
            # Convert to HTML and back to text to clean up markdown
            html = markdown.markdown(content_text)
            soup = BeautifulSoup(html, 'html.parser')
            clean_text = soup.get_text()
            
            # Extract title from filename or content
            title = file_path.stem.replace('-', ' ').replace('_', ' ')
            if 'title' in metadata:
                title = metadata['title']
            
            # Determine if it's a journal entry
            is_journal = file_path.parent.name == 'journals'
            
            # If it's a journal, extract the date
            journal_date = None
            if is_journal:
                # Support multiple Logseq journal filename formats
                # Original: match format like 2024_01_15.md
                date_match = re.search(r'(\d{4})_(\d{2})_(\d{2})', file_path.stem)
                if date_match:
                    year, month, day = date_match.groups()
                    journal_date = f"{year}-{month}-{day}"
                    
                    # Log the matched date for debugging
                    logger.info(f"Found journal date: {journal_date} for file: {file_path}")
            
            # Extract block references and links
            block_refs = re.findall(r'\(\(([a-f0-9-]+)\)\)', content_text)
            links = re.findall(r'\[\[(.*?)\]\]', content_text)
            
            # Extract tags
            tags = re.findall(r'#([A-Za-z0-9_-]+)', content_text)
            
            return {
                'title': title,
                'path': str(file_path),
                'content': content_text,
                'clean_content': clean_text,
                'metadata': metadata,
                'is_journal': is_journal,
                'journal_date': journal_date,
                'block_refs': block_refs,
                'links': links,
                'tags': tags,
                'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None
    
    def parse_all_pages(self):
        """Parse all pages and return as a list"""
        pages = []
        for file_path in self.list_all_pages():
            page = self.parse_file(file_path)
            if page:
                pages.append(page)
        
        logger.info(f"Parsed {len(pages)} pages")
        return pages
    
    def parse_all_journals(self):
        """Parse all journal entries and return as a list"""
        journals = []
        for file_path in self.list_all_journals():
            journal = self.parse_file(file_path)
            if journal:
                journals.append(journal)
                logger.info(f"Journal added: {journal.get('journal_date')} - {file_path.name}")
        
        logger.info(f"Parsed {len(journals)} journal entries")
        return journals
    
    def export_to_json(self, output_path):
        """Export all parsed content to a JSON file"""
        all_content = {
            'pages': self.parse_all_pages(),
            'journals': self.parse_all_journals()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_content, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported all content to {output_path}")
        return output_path

if __name__ == "__main__":
    # Example usage
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import LOGSEQ_NOTES_DIR
    
    parser = LogseqParser(LOGSEQ_NOTES_DIR)
    output_path = Path('./data/processed/logseq_export.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    parser.export_to_json(output_path) 