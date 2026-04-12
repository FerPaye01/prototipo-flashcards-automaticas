import os
import fitz  # PyMuPDF
from docx import Document
from typing import List, Dict, Any

class DocumentProcessor:
    """
    Procesador de documentos (PDF, Word) para extraer texto por páginas o párrafos.
    """
    
    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extrae texto de un PDF página por página.
        """
        pages_content = []
        try:
            doc = fitz.open(pdf_path)
            self._log(f"   📖 PDF abierto: {os.path.basename(pdf_path)} ({len(doc)} páginas)")
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text().strip()
                pages_content.append({
                    "page_number": page_num + 1,
                    "content": text
                })
            doc.close()
            return pages_content
        except Exception as e:
            self._log(f"   ❌ Error al extraer PDF: {e}")
            return []

    def extract_text_from_docx(self, docx_path: str) -> List[Dict[str, Any]]:
        """
        Extrae texto de un archivo Word (.docx). 
        Como Word no tiene páginas fijas, dividimos por párrafos o grupos de párrafos.
        """
        pages_content = []
        try:
            doc = Document(docx_path)
            self._log(f"   📖 Word abierto: {os.path.basename(docx_path)} ({len(doc.paragraphs)} párrafos)")
            
            # Agrupamos párrafos para simular 'páginas' (aprox 500 palabras por 'página')
            current_page_text = []
            word_count = 0
            page_num = 1
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                    
                current_page_text.append(text)
                word_count += len(text.split())
                
                if word_count >= 500:
                    pages_content.append({
                        "page_number": page_num,
                        "content": "\n".join(current_page_text)
                    })
                    current_page_text = []
                    word_count = 0
                    page_num += 1
            
            # Añadir última página si hay contenido
            if current_page_text:
                pages_content.append({
                    "page_number": page_num,
                    "content": "\n".join(current_page_text)
                })
                
            return pages_content
        except Exception as e:
            self._log(f"   ❌ Error al extraer Word: {e}")
            return []

    def segment_pages(self, pages: List[Dict[str, Any]], pages_per_section: int, overlap: int) -> List[Dict[str, Any]]:
        """
        Agrupa páginas en secciones con un solape determinado.
        """
        sections = []
        total_pages = len(pages)
        start = 0
        
        while start < total_pages:
            end = min(start + pages_per_section, total_pages)
            group = pages[start:end]
            
            section_content = ""
            page_range = f"Páginas {group[0]['page_number']}-{group[-1]['page_number']}"
            
            combined_text = []
            for pg in group:
                combined_text.append(f"--- Página {pg['page_number']} ---\n{pg['content']}")
            
            section_content = "\n\n".join(combined_text)
            
            sections.append({
                "title": f"Sección ({page_range})",
                "content": section_content,
                "pages": [pg['page_number'] for pg in group]
            })
            
            if end >= total_pages:
                break
                
            # Avanzar respetando el solape
            start = end - overlap
            if start <= (end - pages_per_section):
                start = end + 1
                
        return sections
