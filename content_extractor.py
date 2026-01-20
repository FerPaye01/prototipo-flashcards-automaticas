# content_extractor.py
# Unified content extractor interface supporting multiple modes

import os
import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

# Import existing extraction modules
from mandar_pdf import extraer_anotaciones_array
from pdf_fulltext_extractor import extract_pdf_fulltext


class ExtractionMode(Enum):
    """Enumeration of supported content extraction modes."""
    PDF_ANNOTATIONS = "pdf_annotations"
    PDF_FULLTEXT = "pdf_fulltext"
    DIRECT_TEXT = "direct_text"


@dataclass
class ExtractionResult:
    """Result of content extraction operation."""
    content: str
    mode: ExtractionMode
    source: str
    metadata: Dict[str, Any]
    timestamp: datetime
    warnings: List[str]


class ContentExtractorInterface(ABC):
    """Abstract interface for content extractors."""
    
    @abstractmethod
    def extract(self, source: str, **kwargs) -> str:
        """Extract content from the given source."""
        pass
    
    @abstractmethod
    def validate_source(self, source: str) -> bool:
        """Validate that the source is compatible with this extractor."""
        pass


class PDFAnnotationExtractor(ContentExtractorInterface):
    """Extractor for PDF annotations and highlights."""
    
    def extract(self, source: str, **kwargs) -> str:
        """
        Extract highlighted/annotated content from PDF.
        
        Args:
            source: Path to PDF file
            
        Returns:
            Extracted annotation text
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid PDF file: {source}")
        
        try:
            annotations = extraer_anotaciones_array(source)
            return "\n".join(annotations) if annotations else ""
        except Exception as e:
            raise Exception(f"Error extracting PDF annotations from {source}: {str(e)}")
    
    def validate_source(self, source: str) -> bool:
        """Validate PDF file exists and is readable."""
        return os.path.isfile(source) and source.lower().endswith('.pdf')


class PDFFullTextExtractor(ContentExtractorInterface):
    """Extractor for complete PDF text content."""
    
    def extract(self, source: str, **kwargs) -> str:
        """
        Extract all text content from PDF.
        
        Args:
            source: Path to PDF file
            
        Returns:
            Extracted full text
        """
        if not self.validate_source(source):
            raise ValueError(f"Invalid PDF file: {source}")
        
        try:
            return extract_pdf_fulltext(source)
        except Exception as e:
            raise Exception(f"Error extracting PDF full text from {source}: {str(e)}")
    
    def validate_source(self, source: str) -> bool:
        """Validate PDF file exists and is readable."""
        return os.path.isfile(source) and source.lower().endswith('.pdf')


class DirectTextExtractor(ContentExtractorInterface):
    """Extractor for direct text input."""
    
    def extract(self, source: str, **kwargs) -> str:
        """
        Process direct text input.
        
        Args:
            source: Text content string
            
        Returns:
            Processed text content
        """
        if not self.validate_source(source):
            raise ValueError("Invalid text input: empty or None")
        
        return self._preprocess_text(source)
    
    def validate_source(self, source: str) -> bool:
        """Validate text input is not empty."""
        return isinstance(source, str) and source.strip() != ""
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess and clean direct text input.
        
        Args:
            text: Raw text input
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive line breaks but preserve paragraph structure
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Clean up common formatting artifacts
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\{\}\"\'\/\\\@\#\$\%\^\&\*\+\=\<\>\~\`\n]', '', text)
        
        return text.strip()


class ContentExtractor:
    """
    Unified content extractor with factory pattern for different extraction methods.
    Supports multiple content sources and processing modes.
    """
    
    def __init__(self):
        self._extractors: Dict[ExtractionMode, ContentExtractorInterface] = {
            ExtractionMode.PDF_ANNOTATIONS: PDFAnnotationExtractor(),
            ExtractionMode.PDF_FULLTEXT: PDFFullTextExtractor(),
            ExtractionMode.DIRECT_TEXT: DirectTextExtractor()
        }
        self._preprocessing_enabled = True
    
    def extract_content(self, source: str, mode: ExtractionMode, **kwargs) -> ExtractionResult:
        """
        Extract content using the specified mode.
        
        Args:
            source: Content source (file path or text string)
            mode: Extraction mode to use
            **kwargs: Additional parameters for extraction
            
        Returns:
            ExtractionResult with content and metadata
        """
        if mode not in self._extractors:
            raise ValueError(f"Unsupported extraction mode: {mode}")
        
        extractor = self._extractors[mode]
        warnings = []
        
        try:
            # Validate source
            if not extractor.validate_source(source):
                raise ValueError(f"Invalid source for mode {mode.value}: {source}")
            
            # Extract content
            content = extractor.extract(source, **kwargs)
            
            # Apply additional preprocessing if enabled
            if self._preprocessing_enabled:
                content, preprocess_warnings = self._apply_preprocessing(content, mode)
                warnings.extend(preprocess_warnings)
            
            # Validate extracted content
            validation_warnings = self._validate_content(content, mode)
            warnings.extend(validation_warnings)
            
            # Create metadata
            metadata = self._create_metadata(source, mode, content, **kwargs)
            
            return ExtractionResult(
                content=content,
                mode=mode,
                source=source,
                metadata=metadata,
                timestamp=datetime.now(),
                warnings=warnings
            )
            
        except Exception as e:
            raise Exception(f"Content extraction failed for {mode.value}: {str(e)}")
    
    def _apply_preprocessing(self, content: str, mode: ExtractionMode) -> tuple[str, List[str]]:
        """
        Apply mode-specific preprocessing to extracted content.
        
        Args:
            content: Raw extracted content
            mode: Extraction mode used
            
        Returns:
            Tuple of (processed_content, warnings)
        """
        warnings = []
        
        if not content or not content.strip():
            warnings.append("Extracted content is empty")
            return "", warnings
        
        # Common preprocessing
        original_length = len(content)
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Normalize line breaks
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        # Mode-specific preprocessing
        if mode == ExtractionMode.PDF_ANNOTATIONS:
            # Clean up annotation artifacts
            content = re.sub(r'\s*\n\s*', '\n', content)
            content = re.sub(r'\n+', '\n\n', content)
        
        elif mode == ExtractionMode.PDF_FULLTEXT:
            # Additional cleanup for full text extraction
            content = self._clean_pdf_artifacts(content)
        
        elif mode == ExtractionMode.DIRECT_TEXT:
            # Minimal processing for direct text
            pass
        
        # Check for significant content loss
        final_length = len(content)
        if original_length > 0 and final_length < original_length * 0.5:
            warnings.append(f"Significant content reduction during preprocessing: {original_length} -> {final_length} characters")
        
        return content.strip(), warnings
    
    def _clean_pdf_artifacts(self, content: str) -> str:
        """
        Clean common PDF extraction artifacts.
        
        Args:
            content: Raw PDF text content
            
        Returns:
            Cleaned content
        """
        # Remove standalone single characters (common OCR artifacts)
        content = re.sub(r'\b[a-zA-Z]\b(?!\s[a-zA-Z]\b)', '', content)
        
        # Remove repeated characters that are likely artifacts
        content = re.sub(r'(.)\1{5,}', r'\1', content)
        
        # Clean up hyphenated words at line breaks
        content = re.sub(r'-\s*\n\s*', '', content)
        
        return content
    
    def _validate_content(self, content: str, mode: ExtractionMode) -> List[str]:
        """
        Validate extracted content and return warnings.
        
        Args:
            content: Extracted content
            mode: Extraction mode used
            
        Returns:
            List of validation warnings
        """
        warnings = []
        
        if not content or not content.strip():
            warnings.append("No content extracted")
            return warnings
        
        # Check minimum content length
        min_lengths = {
            ExtractionMode.PDF_ANNOTATIONS: 10,
            ExtractionMode.PDF_FULLTEXT: 50,
            ExtractionMode.DIRECT_TEXT: 5
        }
        
        min_length = min_lengths.get(mode, 10)
        if len(content.strip()) < min_length:
            warnings.append(f"Extracted content is very short ({len(content)} characters)")
        
        # Check for suspicious patterns
        if len(set(content.replace(' ', '').replace('\n', ''))) < 10:
            warnings.append("Content has very low character diversity (possible extraction error)")
        
        # Check for excessive repetition
        words = content.split()
        if len(words) > 10:
            unique_words = len(set(words))
            if unique_words / len(words) < 0.3:
                warnings.append("Content has high word repetition (possible extraction error)")
        
        return warnings
    
    def _create_metadata(self, source: str, mode: ExtractionMode, content: str, **kwargs) -> Dict[str, Any]:
        """
        Create metadata for extraction result.
        
        Args:
            source: Content source
            mode: Extraction mode
            content: Extracted content
            **kwargs: Additional parameters
            
        Returns:
            Metadata dictionary
        """
        metadata = {
            "extraction_mode": mode.value,
            "content_length": len(content),
            "word_count": len(content.split()) if content else 0,
            "line_count": len(content.splitlines()) if content else 0
        }
        
        # Add source-specific metadata
        if mode in [ExtractionMode.PDF_ANNOTATIONS, ExtractionMode.PDF_FULLTEXT]:
            if os.path.isfile(source):
                metadata.update({
                    "file_size": os.path.getsize(source),
                    "file_name": os.path.basename(source),
                    "file_path": os.path.abspath(source)
                })
        
        # Add any additional kwargs as metadata
        metadata.update(kwargs)
        
        return metadata
    
    def set_preprocessing_enabled(self, enabled: bool):
        """Enable or disable content preprocessing."""
        self._preprocessing_enabled = enabled
    
    def get_supported_modes(self) -> List[ExtractionMode]:
        """Get list of supported extraction modes."""
        return list(self._extractors.keys())
    
    def get_extractor(self, mode: ExtractionMode) -> ContentExtractorInterface:
        """Get the extractor instance for a specific mode."""
        if mode not in self._extractors:
            raise ValueError(f"Unsupported extraction mode: {mode}")
        return self._extractors[mode]


# Convenience functions for backward compatibility
def extract_content(source: str, mode: str) -> str:
    """
    Extract content using string mode identifier.
    
    Args:
        source: Content source
        mode: Mode string ('pdf_annotations', 'pdf_fulltext', 'direct_text')
        
    Returns:
        Extracted content
    """
    try:
        extraction_mode = ExtractionMode(mode)
    except ValueError:
        raise ValueError(f"Invalid extraction mode: {mode}")
    
    extractor = ContentExtractor()
    result = extractor.extract_content(source, extraction_mode)
    return result.content


if __name__ == "__main__":
    # Test the content extractor
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python content_extractor.py <mode> <source>")
        print("Modes: pdf_annotations, pdf_fulltext, direct_text")
        sys.exit(1)
    
    mode_str = sys.argv[1]
    source = sys.argv[2]
    
    try:
        extractor = ContentExtractor()
        mode = ExtractionMode(mode_str)
        result = extractor.extract_content(source, mode)
        
        print(f"Extraction successful!")
        print(f"Mode: {result.mode.value}")
        print(f"Content length: {len(result.content)} characters")
        print(f"Warnings: {result.warnings}")
        print(f"\nFirst 300 characters:")
        print(result.content[:300])
        
    except Exception as e:
        print(f"Error: {e}")