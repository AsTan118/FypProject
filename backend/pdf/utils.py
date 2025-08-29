# pdf/utils.py
import re
import pdfplumber
import io
from typing import List, Dict, Any
from config import CHUNK_SIZE, OVERLAP_SIZE, MIN_CHUNK_LENGTH

def clean_text(text: str, page_num: int = None) -> str:
    """Clean extracted text from PDF"""
    if not text:
        return ""
    text = ' '.join(text.split())
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('™', "'").replace('œ', '"')
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if page_num == 1:
            cleaned_lines.append(line)
            continue
        
        if line.isdigit() or len(line) < 5 or not any(c.isalnum() for c in line):
            continue
        
        cleaned_lines.append(line)
    
    return ' '.join(cleaned_lines)

def split_text_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP_SIZE) -> List[str]:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_size = len(sentence)
        
        if current_size + sentence_size > chunk_size and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)
            
            overlap_size = 0
            overlap_sentences = []
            for sent in reversed(current_chunk):
                overlap_size += len(sent)
                overlap_sentences.insert(0, sent)
                if overlap_size >= overlap:
                    break
            
            current_chunk = overlap_sentences
            current_size = sum(len(s) for s in current_chunk)
        
        current_chunk.append(sentence)
        current_size += sentence_size
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def extract_text_from_pdf(pdf_content: bytes) -> List[Dict[str, Any]]:
    """Extract text from PDF"""
    chunks = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                
                cleaned_text = clean_text(text, page_num=page_num)
                if not cleaned_text:
                    continue
                
                text_chunks = split_text_into_chunks(cleaned_text)
                
                for chunk_index, chunk_text in enumerate(text_chunks):
                    if len(chunk_text) > MIN_CHUNK_LENGTH:
                        chunks.append({
                            "page": page_num,
                            "chunk": chunk_index,
                            "text": chunk_text
                        })
    
    except Exception as e:
        print(f"Error extracting text: {e}")
        raise
    
    return chunks