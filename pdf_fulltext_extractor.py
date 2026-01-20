# pdf_fulltext_extractor.py
# Full-text PDF extraction functionality

import fitz  # PyMuPDF
import re
from typing import List, Optional, Tuple


class PDFFullTextExtractor:
    """
    Extracts all text content from PDF files with support for multi-column layouts
    and filtering of headers, footers, and page numbers.
    """
    
    def __init__(self):
        self.header_footer_threshold = 0.1  # Top/bottom 10% of page considered header/footer area
        self.min_text_length = 3  # Minimum length for text to be considered content
        
    def extract_fulltext(self, pdf_path: str) -> str:
        """
        Extract all text content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content as a single string
        """
        try:
            pdf_document = fitz.open(pdf_path)
            all_text = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                page_text = self._extract_page_text(page, page_num)
                if page_text.strip():
                    all_text.append(page_text)
            
            pdf_document.close()
            return "\n\n".join(all_text)
            
        except Exception as e:
            raise Exception(f"Error extracting text from PDF {pdf_path}: {str(e)}")
    
    def _extract_page_text(self, page: fitz.Page, page_num: int) -> str:
        """
        Extract text from a single page with filtering and structure preservation.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number for context
            
        Returns:
            Cleaned text content from the page
        """
        # Get page dimensions
        page_rect = page.rect
        page_height = page_rect.height
        page_width = page_rect.width
        
        # Define header/footer regions
        header_y = page_height * self.header_footer_threshold
        footer_y = page_height * (1 - self.header_footer_threshold)
        
        # Extract text blocks with position information
        text_blocks = page.get_text("dict")
        
        content_blocks = []
        
        for block in text_blocks["blocks"]:
            if "lines" not in block:
                continue
                
            block_text = self._extract_block_text(block, header_y, footer_y, page_num)
            if block_text:
                content_blocks.append(block_text)
        
        # Sort blocks by vertical position to maintain reading order
        content_blocks.sort(key=lambda x: x[1])  # Sort by y-coordinate
        
        # Extract just the text content
        page_text = "\n".join([block[0] for block in content_blocks])
        
        # Clean up the text
        return self._clean_text(page_text)
    
    def _extract_block_text(self, block: dict, header_y: float, footer_y: float, page_num: int) -> Optional[Tuple[str, float]]:
        """
        Extract text from a text block, filtering headers/footers and page numbers.
        
        Args:
            block: Text block dictionary from PyMuPDF
            header_y: Y-coordinate threshold for header region
            footer_y: Y-coordinate threshold for footer region
            page_num: Current page number
            
        Returns:
            Tuple of (text_content, y_coordinate) or None if filtered out
        """
        block_lines = []
        block_y = float('inf')
        
        for line in block["lines"]:
            line_y = line["bbox"][1]  # Top y-coordinate of line
            block_y = min(block_y, line_y)
            
            # Skip header and footer regions
            if line_y < header_y or line_y > footer_y:
                continue
            
            line_text = ""
            for span in line["spans"]:
                span_text = span["text"].strip()
                if span_text:
                    line_text += span_text + " "
            
            line_text = line_text.strip()
            if line_text and len(line_text) >= self.min_text_length:
                # Filter out likely page numbers
                if not self._is_page_number(line_text, page_num):
                    block_lines.append(line_text)
        
        if block_lines:
            return (" ".join(block_lines), block_y)
        return None
    
    def _is_page_number(self, text: str, page_num: int) -> bool:
        """
        Determine if text is likely a page number.
        
        Args:
            text: Text to check
            page_num: Current page number
            
        Returns:
            True if text appears to be a page number
        """
        # Remove whitespace and check if it's just numbers
        clean_text = text.strip()
        
        # Check if it's just a number
        if clean_text.isdigit():
            num = int(clean_text)
            # Allow some flexibility around the actual page number
            if abs(num - (page_num + 1)) <= 2:
                return True
        
        # Check for common page number patterns
        page_patterns = [
            r'^\d+$',  # Just a number
            r'^page\s+\d+$',  # "page 5"
            r'^\d+\s*/\s*\d+$',  # "5 / 10"
            r'^-\s*\d+\s*-$',  # "- 5 -"
        ]
        
        for pattern in page_patterns:
            if re.match(pattern, clean_text.lower()):
                return True
        
        return False
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive line breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Clean up common PDF artifacts
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\{\}\"\'\/\\\@\#\$\%\^\&\*\+\=\<\>\~\`]', '', text)
        
        # Remove standalone single characters that are likely artifacts
        text = re.sub(r'\b[a-zA-Z]\b(?!\s[a-zA-Z]\b)', '', text)
        
        return text.strip()


# Convenience function for backward compatibility
def extract_pdf_fulltext(pdf_path: str) -> str:
    """
    Extract all text content from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text content as a single string
    """
    extractor = PDFFullTextExtractor()
    return extractor.extract_fulltext(pdf_path)


if __name__ == "__main__":
    # Test the extractor
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        try:
            text = extract_pdf_fulltext(pdf_path)
            print(f"Extracted {len(text)} characters from {pdf_path}")
            print("\nFirst 500 characters:")
            print(text[:500])
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python pdf_fulltext_extractor.py <pdf_file>")