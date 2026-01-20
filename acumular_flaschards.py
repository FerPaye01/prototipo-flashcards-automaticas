#acumular_flashcards.py
"""
Enhanced flashcard accumulation module with support for multiple input sources.
Updated to work with the new unified content processing system while maintaining
backward compatibility with existing functionality.
"""

import time
import logging
from typing import List, Tuple, Optional, Dict, Any, Union
from enum import Enum

# Import improved modules
from improved_text_segmenter import ImprovedTextSegmenter, dividir_texto_en_fragmentos
from mandar_pdf import extraer_anotaciones_array
from generar_flashcards import generar_flashcards_parametrizadas
from logica_limites_flashcards import salida_flashcards
from automatizar_importacion import procesar_importacion_automática

# Import new input system components
try:
    from unified_content_processor import ProcessingPipelineIntegration, InputMode, ProcessingResult
    from content_extractor import ContentExtractor, ExtractionMode
    from direct_text_processor import DirectTextIntegration
    UNIFIED_SYSTEM_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Unified system components not available: {e}")
    UNIFIED_SYSTEM_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class InputSource(Enum):
    """Enumeration of supported input sources."""
    PDF_ANNOTATIONS = "pdf_annotations"
    PDF_FULLTEXT = "pdf_fulltext"
    DIRECT_TEXT = "direct_text"
    FILE_PATH = "file_path"  # Legacy support


def procesar_texto_segmentado(source: Union[str, List[str]], input_source: InputSource = InputSource.PDF_ANNOTATIONS, 
                            progress_callback: Optional[callable] = None) -> List[str]:
    """
    Enhanced text processing function that supports multiple input sources.
    
    Args:
        source: Input source (file path, text content, or list of files)
        input_source: Type of input source
        progress_callback: Optional callback for progress updates
        
    Returns:
        List of flashcard batches
        
    Raises:
        ValueError: If input source is invalid or content cannot be extracted
        RuntimeError: If processing fails
    """
    try:
        # Extract content based on input source
        if input_source == InputSource.PDF_ANNOTATIONS:
            if isinstance(source, list):
                # Multiple PDF files with annotations
                all_content = []
                for pdf_path in source:
                    material_array = extraer_anotaciones_array(pdf_path)
                    if material_array:
                        all_content.extend(material_array)
                material_estudio = "\n".join(all_content)
            else:
                # Single PDF file with annotations (legacy behavior)
                material_array = extraer_anotaciones_array(source)
                material_estudio = "\n".join(material_array)
                
        elif input_source == InputSource.PDF_FULLTEXT:
            # Use unified system for full text extraction
            if UNIFIED_SYSTEM_AVAILABLE:
                extractor = ContentExtractor()
                if isinstance(source, list):
                    all_content = []
                    for pdf_path in source:
                        result = extractor.extract_content(pdf_path, ExtractionMode.PDF_FULLTEXT)
                        if result.content:
                            all_content.append(result.content)
                    material_estudio = "\n\n".join(all_content)
                else:
                    result = extractor.extract_content(source, ExtractionMode.PDF_FULLTEXT)
                    material_estudio = result.content
            else:
                raise RuntimeError("PDF full text extraction requires unified system components")
                
        elif input_source == InputSource.DIRECT_TEXT:
            # Direct text input
            if isinstance(source, str):
                material_estudio = source
            else:
                raise ValueError("Direct text input must be a string")
                
        elif input_source == InputSource.FILE_PATH:
            # Legacy file path support - assume PDF annotations
            material_array = extraer_anotaciones_array(source)
            material_estudio = "\n".join(material_array)
            
        else:
            raise ValueError(f"Unsupported input source: {input_source}")
        
        # Validate extracted content
        if not material_estudio or not material_estudio.strip():
            raise ValueError("No content extracted from input source")
        
        logger.info(f"Extracted {len(material_estudio)} characters from {input_source.value}")
        
        # Use improved text segmentation
        try:
            segmenter = ImprovedTextSegmenter()
            segmentation_result = segmenter.segment_text(material_estudio)
            partes = segmentation_result.segments
            
            # Log segmentation warnings
            if segmentation_result.warnings:
                for warning in segmentation_result.warnings:
                    logger.warning(f"Segmentation warning: {warning}")
            
            logger.info(f"Text segmented into {len(partes)} parts using {segmentation_result.segmentation_method}")
            
        except Exception as e:
            logger.warning(f"Improved segmentation failed, falling back to legacy: {e}")
            # Fallback to legacy segmentation
            partes = dividir_texto_en_fragmentos(material_estudio)
        
        if not partes:
            raise RuntimeError("Text segmentation produced no segments")
        
        # Process each segment to generate flashcards
        lotes_flashcards_tab = []
        total_parts = len(partes)
        
        for i, (parte, tokens) in enumerate(partes, 1):
            try:
                logger.info(f"Processing part {i}/{total_parts} with {tokens} tokens")
                
                # Update progress if callback provided
                if progress_callback:
                    progress = (i - 1) / total_parts
                    progress_callback(f"Processing segment {i}/{total_parts}", progress)
                
                # Calculate flashcard count for this segment
                num_flashcards = salida_flashcards(tokens)
                
                # Generate flashcards with error handling
                flashcards, metadatos = generar_flashcards_parametrizadas(parte, num_flashcards)
                
                if flashcards:
                    lotes_flashcards_tab.append(flashcards)
                    logger.info(f"Generated flashcards for part {i}: {len(flashcards.split(chr(10)))} cards")
                else:
                    logger.warning(f"No flashcards generated for part {i}")
                
                # API delay between segments (except for last segment)
                if i < total_parts:
                    logger.debug(f"Waiting 60 seconds before next API call...")
                    time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error processing segment {i}: {e}")
                # Continue with other segments rather than failing completely
                continue
        
        if not lotes_flashcards_tab:
            raise RuntimeError("No flashcards were generated from any segments")
        
        logger.info(f"Successfully processed {len(lotes_flashcards_tab)} segments")
        return lotes_flashcards_tab
        
    except Exception as e:
        logger.error(f"Text processing failed: {e}")
        raise
def acumular_total_flashacards(source: Union[str, List[str]], input_source: InputSource = InputSource.PDF_ANNOTATIONS,
                             progress_callback: Optional[callable] = None) -> str:
    """
    Enhanced flashcard accumulation function with support for multiple input sources.
    
    Args:
        source: Input source (file path, text content, or list of files)
        input_source: Type of input source
        progress_callback: Optional callback for progress updates
        
    Returns:
        Combined flashcards text ready for Anki import
        
    Raises:
        ValueError: If input is invalid
        RuntimeError: If processing fails
    """
    try:
        logger.info(f"Starting flashcard accumulation from {input_source.value}")
        
        # Process text and generate flashcard batches
        lotes_flashcards_en_array = procesar_texto_segmentado(source, input_source, progress_callback)
        
        if not lotes_flashcards_en_array:
            raise RuntimeError("No flashcard batches were generated")
        
        # Combine all flashcard batches
        total_flashcards_joined = "\n".join(lotes_flashcards_en_array)
        
        # Count total flashcards
        flashcard_count = len([line for line in total_flashcards_joined.split('\n') if '\t' in line])
        logger.info(f"Accumulated {flashcard_count} total flashcards")
        
        return total_flashcards_joined
        
    except Exception as e:
        logger.error(f"Flashcard accumulation failed: {e}")
        raise


def acumular_total_flashacards_legacy(path_pdf: str) -> str:
    """
    Legacy function for backward compatibility.
    Maintains the original interface for existing code.
    
    Args:
        path_pdf: Path to PDF file
        
    Returns:
        Combined flashcards text
    """
    return acumular_total_flashacards(path_pdf, InputSource.PDF_ANNOTATIONS)

def process_with_unified_system(input_mode: str, source: Union[str, List[str]], 
                              progress_callback: Optional[callable] = None) -> Dict[str, Any]:
    """
    Process content using the unified content processing system.
    
    Args:
        input_mode: Input mode ("pdf_annotations", "pdf_fulltext", "direct_text")
        source: Input source
        progress_callback: Optional progress callback
        
    Returns:
        Dictionary with processing results
        
    Raises:
        RuntimeError: If unified system is not available or processing fails
    """
    if not UNIFIED_SYSTEM_AVAILABLE:
        raise RuntimeError("Unified content processing system is not available")
    
    try:
        # Map input mode to InputMode enum
        mode_mapping = {
            "pdf_annotations": InputMode.PDF_ANNOTATIONS,
            "pdf_fulltext": InputMode.PDF_FULLTEXT,
            "direct_text": InputMode.DIRECT_TEXT
        }
        
        if input_mode not in mode_mapping:
            raise ValueError(f"Unsupported input mode: {input_mode}")
        
        unified_mode = mode_mapping[input_mode]
        
        # Create integration and process
        integration = ProcessingPipelineIntegration()
        
        if progress_callback:
            def unified_progress_callback(state):
                progress_callback(f"{state.stage.value}: {state.current_item or 'Processing...'}", state.progress)
            
            result = integration.process_with_progress_reporting(
                unified_mode, source, unified_progress_callback
            )
        else:
            result = integration.get_processor().process_content(unified_mode, source)
        
        if result.success:
            return {
                "success": True,
                "flashcard_count": result.flashcard_count,
                "segment_count": result.segment_count,
                "processing_time": result.processing_time,
                "warnings": result.warnings,
                "deck_name": result.deck_name
            }
        else:
            raise RuntimeError(f"Unified processing failed: {result.error}")
            
    except Exception as e:
        logger.error(f"Unified system processing failed: {e}")
        raise


def validate_input_source(source: Union[str, List[str]], input_source: InputSource) -> Tuple[bool, str]:
    """
    Validate input source before processing.
    
    Args:
        source: Input source to validate
        input_source: Type of input source
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if input_source == InputSource.DIRECT_TEXT:
            if not isinstance(source, str) or not source.strip():
                return False, "Direct text input cannot be empty"
            
            # Check minimum content length
            if len(source.strip()) < 10:
                return False, "Direct text input is too short (minimum 10 characters)"
                
        elif input_source in [InputSource.PDF_ANNOTATIONS, InputSource.PDF_FULLTEXT, InputSource.FILE_PATH]:
            if isinstance(source, list):
                # Multiple files
                if not source:
                    return False, "No files provided"
                
                for file_path in source:
                    if not isinstance(file_path, str):
                        return False, f"Invalid file path: {file_path}"
                    
                    if not file_path.endswith('.pdf'):
                        return False, f"File is not a PDF: {file_path}"
                    
                    # Check if file exists (basic validation)
                    try:
                        with open(file_path, 'rb') as f:
                            # Try to read first few bytes to verify it's accessible
                            f.read(4)
                    except (IOError, OSError) as e:
                        return False, f"Cannot access file {file_path}: {str(e)}"
            else:
                # Single file
                if not isinstance(source, str):
                    return False, "File path must be a string"
                
                if not source.endswith('.pdf'):
                    return False, "File is not a PDF"
                
                try:
                    with open(source, 'rb') as f:
                        f.read(4)
                except (IOError, OSError) as e:
                    return False, f"Cannot access file {source}: {str(e)}"
        
        else:
            return False, f"Unsupported input source: {input_source}"
        
        return True, ""
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"


# Backward compatibility functions
def procesar_texto_segmentado_legacy(path_pdf: str) -> List[str]:
    """Legacy function for backward compatibility."""
    return procesar_texto_segmentado(path_pdf, InputSource.PDF_ANNOTATIONS)


if __name__ == "__main__":
    # Demo usage with enhanced error handling
    import sys
    
    def demo_progress(message: str, progress: float):
        print(f"Progress: {progress:.1%} - {message}")
    
    try:
        # Test with different input sources
        if len(sys.argv) > 1:
            test_file = sys.argv[1]
            
            # Validate input
            is_valid, error = validate_input_source(test_file, InputSource.PDF_ANNOTATIONS)
            if not is_valid:
                print(f"Validation failed: {error}")
                sys.exit(1)
            
            print(f"Processing {test_file} with enhanced system...")
            
            # Process with enhanced system
            flashcards_f = acumular_total_flashacards(
                test_file, 
                InputSource.PDF_ANNOTATIONS, 
                demo_progress
            )
            
            # Import to Anki
            print("Importing to Anki...")
            procesar_importacion_automática(flashcards_f)
            print("Processing completed successfully!")
            
        else:
            # Test with demo text
            demo_text = """
            Artificial intelligence (AI) is intelligence demonstrated by machines, 
            in contrast to the natural intelligence displayed by humans and animals. 
            Leading AI textbooks define the field as the study of "intelligent agents": 
            any device that perceives its environment and takes actions that maximize 
            its chance of successfully achieving its goals.
            """
            
            print("Testing with direct text input...")
            flashcards_f = acumular_total_flashacards(
                demo_text, 
                InputSource.DIRECT_TEXT, 
                demo_progress
            )
            
            print(f"Generated flashcards:\n{flashcards_f[:500]}...")
            
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)
