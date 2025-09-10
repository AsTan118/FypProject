# pdf/processor.py - Enhanced version with better text processing
import os
import pdfplumber
from typing import List, Dict, Tuple
from database import get_db_connection
import time
import re
from config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_LENGTH

class PDFProcessor:
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        """
        Initialize PDF processor with configurable parameters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = MIN_CHUNK_LENGTH

    def clean_text(self, text: str) -> str:
        """Enhanced text cleaning for better quality"""
        if not text:
            return ""
        
        # Fix common PDF extraction issues
        text = text.replace('\x00', '')  # Remove null bytes
        text = text.replace('ﬁ', 'fi')  # Fix ligatures
        text = text.replace('ﬂ', 'fl')
        text = text.replace('ﬀ', 'ff')
        text = text.replace('ﬃ', 'ffi')
        text = text.replace('ﬄ', 'ffl')
        
        # Fix hyphenation at line breaks
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        
        # Normalize whitespace but preserve paragraph breaks
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Remove excessive spaces within lines
                line = ' '.join(line.split())
                cleaned_lines.append(line)
            elif cleaned_lines and cleaned_lines[-1]:
                # Preserve paragraph breaks
                cleaned_lines.append('')
        
        # Join lines, preserving paragraph structure
        text = '\n'.join(cleaned_lines)
        
        # Remove multiple consecutive blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text

    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[List[Dict], int]:
        """
        Enhanced text extraction with better error handling and structure preservation
        """
        chunks = []
        total_pages = 0
        
        try:
            if not os.path.exists(pdf_path):
                print(f"PDF file not found: {pdf_path}")
                return [], 0
            
            file_size = os.path.getsize(pdf_path)
            print(f"Processing PDF: {pdf_path} (Size: {file_size:,} bytes)")
            
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                print(f"PDF has {total_pages} pages")
                
                # Extract text from all pages first
                full_text = ""
                page_texts = []
                
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        # Extract text with layout preservation
                        text = page.extract_text()
                        
                        if text:
                            cleaned = self.clean_text(text)
                            if cleaned:
                                page_texts.append({
                                    'text': cleaned,
                                    'page': page_num
                                })
                                full_text += f"\n[Page {page_num}]\n{cleaned}\n"
                        
                    except Exception as e:
                        print(f"Error extracting text from page {page_num}: {e}")
                        continue
                
                if not page_texts:
                    print("No text extracted from PDF")
                    return [], total_pages
                
                # Create intelligent chunks that preserve context
                chunks = self._create_intelligent_chunks(full_text, page_texts, os.path.basename(pdf_path))
                
                print(f"Created {len(chunks)} chunks from {total_pages} pages")
                return chunks, total_pages
                
        except Exception as e:
            print(f"Error processing PDF {pdf_path}: {e}")
            return chunks, total_pages

    def _create_intelligent_chunks(self, full_text: str, page_texts: List[Dict], filename: str) -> List[Dict]:
        """Create chunks that preserve semantic meaning and context"""
        chunks = []
        
        # Split by major sections (if identifiable)
        sections = self._identify_sections(full_text)
        
        if sections:
            # Process each section separately
            for section in sections:
                section_chunks = self._split_text_into_chunks(section['text'])
                for chunk in section_chunks:
                    chunks.append({
                        'content': chunk,
                        'page': section.get('page', 1),
                        'metadata': {
                            'filename': filename,
                            'page': section.get('page', 1),
                            'section': section.get('title', 'Main Content'),
                            'total_pages': len(page_texts)
                        }
                    })
        else:
            # Fall back to page-based chunking with overlap
            current_chunk = ""
            current_page = 1
            
            for page_info in page_texts:
                page_text = page_info['text']
                page_num = page_info['page']
                
                # Add page text to current chunk
                if len(current_chunk) + len(page_text) <= self.chunk_size:
                    current_chunk += f"\n{page_text}"
                    current_page = page_num
                else:
                    # Split the page text if needed
                    if current_chunk:
                        chunks.append({
                            'content': current_chunk.strip(),
                            'page': current_page,
                            'metadata': {
                                'filename': filename,
                                'page': current_page,
                                'total_pages': len(page_texts)
                            }
                        })
                    
                    # Process the current page text
                    page_chunks = self._split_text_into_chunks(page_text)
                    for chunk in page_chunks:
                        chunks.append({
                            'content': chunk,
                            'page': page_num,
                            'metadata': {
                                'filename': filename,
                                'page': page_num,
                                'total_pages': len(page_texts)
                            }
                        })
                    
                    current_chunk = ""
            
            # Add any remaining text
            if current_chunk.strip():
                chunks.append({
                    'content': current_chunk.strip(),
                    'page': current_page,
                    'metadata': {
                        'filename': filename,
                        'page': current_page,
                        'total_pages': len(page_texts)
                    }
                })
        
        return chunks

    def _identify_sections(self, text: str) -> List[Dict]:
        """Identify logical sections in the document"""
        sections = []
        
        # Common section patterns
        section_patterns = [
            r'^#{1,3}\s+(.+)$',  # Markdown headers
            r'^(\d+\.?\d*)\s+([A-Z][^.]+)$',  # Numbered sections
            r'^([A-Z][A-Z\s]+)$',  # All caps headers
            r'^(Chapter|Section|Part)\s+\d+',  # Chapter markers
        ]
        
        lines = text.split('\n')
        current_section = {'title': 'Introduction', 'text': '', 'page': 1}
        
        for line in lines:
            # Check if line matches section pattern
            is_section = False
            for pattern in section_patterns:
                if re.match(pattern, line.strip()):
                    # Save current section if it has content
                    if current_section['text'].strip():
                        sections.append(current_section)
                    
                    # Start new section
                    current_section = {
                        'title': line.strip(),
                        'text': '',
                        'page': self._extract_page_number(line) or current_section.get('page', 1)
                    }
                    is_section = True
                    break
            
            if not is_section:
                current_section['text'] += line + '\n'
        
        # Add final section
        if current_section['text'].strip():
            sections.append(current_section)
        
        return sections if len(sections) > 1 else []

    def _extract_page_number(self, text: str) -> int:
        """Extract page number from text if present"""
        page_match = re.search(r'\[Page (\d+)\]', text)
        if page_match:
            return int(page_match.group(1))
        return None

    def _split_text_into_chunks(self, text: str) -> List[str]:
        """
        Enhanced chunking that preserves semantic units
        """
        if not text or len(text) <= self.chunk_size:
            return [text] if len(text) > self.min_chunk_length else []
        
        chunks = []
        
        # Try to split by paragraphs first
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If paragraph is too large, split it further
            if len(para) > self.chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # Split large paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                        current_chunk += sentence + " "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + " "
            
            # If adding paragraph doesn't exceed limit
            elif len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += para + "\n\n"
            
            # Save current chunk and start new one
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap
                if chunks and self.chunk_overlap > 0:
                    # Get last sentences from previous chunk for overlap
                    last_chunk = chunks[-1]
                    sentences = re.split(r'(?<=[.!?])\s+', last_chunk)
                    
                    overlap_text = ""
                    for sent in reversed(sentences):
                        if len(overlap_text) + len(sent) <= self.chunk_overlap:
                            overlap_text = sent + " " + overlap_text
                        else:
                            break
                    
                    current_chunk = overlap_text + para + "\n\n"
                else:
                    current_chunk = para + "\n\n"
        
        # Add final chunk
        if current_chunk and len(current_chunk) > self.min_chunk_length:
            chunks.append(current_chunk.strip())
        
        return chunks

    def process_pdf(self, pdf_id: int, pdf_path: str) -> bool:
        """
        Process a PDF file and store chunks in database
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            print(f"Processing PDF {pdf_id} from path: {pdf_path}")
            start_time = time.time()
            
            # Extract text chunks with enhanced processing
            text_chunks, page_count = self.extract_text_from_pdf(pdf_path)
            
            if not text_chunks:
                print(f"No text chunks extracted from PDF {pdf_id}")
                cursor.execute('''
                    UPDATE pdfs 
                    SET processing_status = 'completed', 
                        page_count = 0,
                        processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (pdf_id,))
                conn.commit()
                return True
            
            # Update page count
            cursor.execute('''
                UPDATE pdfs 
                SET page_count = ?
                WHERE id = ?
            ''', (page_count, pdf_id))
            
            # Prepare chunks for batch insert
            chunk_data = []
            for i, chunk in enumerate(text_chunks):
                # Ensure chunk content is not too large for database
                content = chunk['content'][:5000] if len(chunk['content']) > 5000 else chunk['content']
                
                chunk_data.append((
                    pdf_id, 
                    i, 
                    content, 
                    chunk['page'], 
                    str(chunk['metadata'])
                ))
            
            # Insert all chunks at once
            cursor.executemany('''
                INSERT INTO pdf_chunks (pdf_id, chunk_index, content, page_number, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', chunk_data)
            
            # Update processing status to completed
            cursor.execute('''
                UPDATE pdfs 
                SET processing_status = 'completed',
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (pdf_id,))
            
            conn.commit()
            
            processing_time = time.time() - start_time
            print(f"Successfully processed PDF {pdf_id}:")
            print(f"  - Pages: {page_count}")
            print(f"  - Chunks: {len(text_chunks)}")
            print(f"  - Time: {processing_time:.2f}s")
            print(f"  - Avg chunk size: {sum(len(c['content']) for c in text_chunks) / len(text_chunks):.0f} chars")
            
            return True
            
        except Exception as e:
            print(f"Error processing PDF {pdf_id}: {e}")
            
            # Mark as completed to avoid stuck state
            try:
                cursor.execute('''
                    UPDATE pdfs 
                    SET processing_status = 'completed',
                        processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (pdf_id,))
                conn.commit()
            except:
                pass
            
            return False
            
        finally:
            conn.close()