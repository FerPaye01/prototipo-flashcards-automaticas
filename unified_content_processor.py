"""
Unified Content Processing Pipeline

This module provides a single processing workflow that handles all input types
(PDF annotations, PDF full text, direct text) with consistent error handling
and content routing based on input method selection.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable, List, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import traceback

# Import existing processing modules
from content_extractor import ContentExtractor, ExtractionMode
from direct_text_processor import DirectTextIntegration
from input_method_controller import InputMode
from segmentar_entrada_variable import dividir_texto_en_fragmentos
from generar_flashcards import generar_flashcards_parametrizadas
from logica_limites_flashcards import salida_flashcards
from automatizar_importacion import procesar_importacion_automática


class ProcessingStage(Enum):
    """Enumeration of processing stages."""
    INITIALIZATION = "initialization"
    CONTENT_EXTRACTION = "content_extraction"
    TEXT_SEGMENTATION = "text_segmentation"
    FLASHCARD_GENERATION = "flashcard_generation"
    ANKI_IMPORT = "anki_import"
    COMPLETION = "completion"


@dataclass
class ProcessingState:
    """Current state of processing operation."""
    stage: ProcessingStage
    progress: float  # 0.0 to 1.0
    current_item: Optional[str] = None
    total_items: int = 0
    processed_items: int = 0
    error: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class ProcessingResult:
    """Result of content processing operation."""
    success: bool
    input_mode: InputMode
    source_info: Dict[str, Any]
    flashcard_count: int
    segment_count: int
    processing_time: float
    deck_name: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}


class UnifiedContentProcessor:
    """
    Unified content processing pipeline that handles all input types
    with consistent error handling and progress reporting.
    """
    
    def __init__(self):
        """Initialize the unified content processor."""
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.content_extractor = ContentExtractor()
        self.direct_text_integration = DirectTextIntegration()
        
        # Processing configuration
        self.api_delay = 60  # Delay between API calls (seconds)
        self.max_retries = 3
        self.timeout = 300  # Maximum processing time per item (seconds)
        
        # State tracking
        self.current_state = None
        self.is_processing = False
        self.should_cancel = False
        
        # Progress callbacks
        self.progress_callbacks: List[Callable[[ProcessingState], None]] = []
    
    def register_progress_callback(self, callback: Callable[[ProcessingState], None]):
        """
        Register a callback for progress updates.
        
        Args:
            callback: Function to call with ProcessingState updates
        """
        self.progress_callbacks.append(callback)
    
    def _update_progress(self, stage: ProcessingStage, progress: float, **kwargs):
        """
        Update processing state and notify callbacks.
        
        Args:
            stage: Current processing stage
            progress: Progress value (0.0 to 1.0)
            **kwargs: Additional state parameters
        """
        self.current_state = ProcessingState(
            stage=stage,
            progress=progress,
            **kwargs
        )
        
        # Notify all callbacks
        for callback in self.progress_callbacks:
            try:
                callback(self.current_state)
            except Exception as e:
                self.logger.error(f"Error in progress callback: {e}")
    
    def process_content(
        self,
        input_mode: InputMode,
        source: Any,
        processing_options: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process content through the unified pipeline.
        
        Args:
            input_mode: Type of input being processed
            source: Content source (file path, text, or list of files)
            processing_options: Additional processing options
            
        Returns:
            ProcessingResult with outcome and metadata
        """
        start_time = time.time()
        self.is_processing = True
        self.should_cancel = False
        
        try:
            self._update_progress(ProcessingStage.INITIALIZATION, 0.0)
            
            # Route to appropriate processing method
            if input_mode == InputMode.DIRECT_TEXT:
                result = self._process_direct_text(source, processing_options or {})
            elif input_mode in [InputMode.PDF_ANNOTATIONS, InputMode.PDF_FULLTEXT]:
                if isinstance(source, list):
                    result = self._process_multiple_files(input_mode, source, processing_options or {})
                else:
                    result = self._process_single_file(input_mode, source, processing_options or {})
            else:
                raise ValueError(f"Unsupported input mode: {input_mode}")
            
            # Add processing time
            result.processing_time = time.time() - start_time
            
            self._update_progress(ProcessingStage.COMPLETION, 1.0)
            return result
            
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            self.logger.debug(traceback.format_exc())
            
            return ProcessingResult(
                success=False,
                input_mode=input_mode,
                source_info={"source": str(source)},
                flashcard_count=0,
                segment_count=0,
                processing_time=time.time() - start_time,
                error=str(e)
            )
        
        finally:
            self.is_processing = False
    
    def _process_direct_text(self, text: str, options: Dict[str, Any]) -> ProcessingResult:
        """
        Process direct text input.
        
        Args:
            text: Input text content
            options: Processing options
            
        Returns:
            ProcessingResult
        """
        self._update_progress(
            ProcessingStage.CONTENT_EXTRACTION,
            0.1,
            current_item="Direct text input",
            total_items=1,
            processed_items=0
        )
        
        # Validate and extract content
        extraction_mode = ExtractionMode.DIRECT_TEXT
        extraction_result = self.content_extractor.extract_content(text, extraction_mode)
        
        if not extraction_result.content:
            raise ValueError("No content extracted from direct text input")
        
        # Process through the pipeline
        return self._process_extracted_content(
            content=extraction_result.content,
            input_mode=InputMode.DIRECT_TEXT,
            source_info={
                "type": "direct_text",
                "length": len(text),
                "word_count": len(text.split())
            },
            extraction_metadata=extraction_result.metadata
        )
    
    def _process_single_file(self, input_mode: InputMode, file_path: str, options: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single file.
        
        Args:
            input_mode: PDF processing mode
            file_path: Path to file
            options: Processing options
            
        Returns:
            ProcessingResult
        """
        self._update_progress(
            ProcessingStage.CONTENT_EXTRACTION,
            0.1,
            current_item=file_path,
            total_items=1,
            processed_items=0
        )
        
        # Map input mode to extraction mode
        extraction_mode = self._map_input_to_extraction_mode(input_mode)
        
        # Extract content
        extraction_result = self.content_extractor.extract_content(file_path, extraction_mode)
        
        if not extraction_result.content:
            raise ValueError(f"No content extracted from file: {file_path}")
        
        # Process through the pipeline
        return self._process_extracted_content(
            content=extraction_result.content,
            input_mode=input_mode,
            source_info={
                "type": "single_file",
                "file_path": file_path,
                "file_name": extraction_result.metadata.get("file_name", "unknown")
            },
            extraction_metadata=extraction_result.metadata
        )
    
    def _process_multiple_files(self, input_mode: InputMode, file_paths: List[str], options: Dict[str, Any]) -> ProcessingResult:
        """
        Process multiple files.
        
        Args:
            input_mode: PDF processing mode
            file_paths: List of file paths
            options: Processing options
            
        Returns:
            ProcessingResult
        """
        total_files = len(file_paths)
        all_content = []
        all_warnings = []
        processed_files = 0
        
        # Map input mode to extraction mode
        extraction_mode = self._map_input_to_extraction_mode(input_mode)
        
        # Process each file
        for i, file_path in enumerate(file_paths):
            if self.should_cancel:
                raise RuntimeError("Processing cancelled by user")
            
            self._update_progress(
                ProcessingStage.CONTENT_EXTRACTION,
                0.1 + (i / total_files) * 0.2,  # 10-30% for extraction
                current_item=file_path,
                total_items=total_files,
                processed_items=i
            )
            
            try:
                # Extract content from file
                extraction_result = self.content_extractor.extract_content(file_path, extraction_mode)
                
                if extraction_result.content:
                    all_content.append(extraction_result.content)
                    all_warnings.extend(extraction_result.warnings)
                    processed_files += 1
                else:
                    all_warnings.append(f"No content extracted from {file_path}")
                
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {e}")
                all_warnings.append(f"Failed to process {file_path}: {str(e)}")
        
        if not all_content:
            raise ValueError("No content extracted from any files")
        
        # Combine all content
        combined_content = "\n\n".join(all_content)
        
        # Process through the pipeline
        result = self._process_extracted_content(
            content=combined_content,
            input_mode=input_mode,
            source_info={
                "type": "multiple_files",
                "file_count": total_files,
                "processed_files": processed_files,
                "file_paths": file_paths
            },
            extraction_metadata={"combined_from_files": processed_files}
        )
        
        # Add file processing warnings
        result.warnings.extend(all_warnings)
        return result
    
    def _process_extracted_content(
        self,
        content: str,
        input_mode: InputMode,
        source_info: Dict[str, Any],
        extraction_metadata: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Process extracted content through segmentation, generation, and import.
        
        Args:
            content: Extracted text content
            input_mode: Original input mode
            source_info: Information about content source
            extraction_metadata: Metadata from extraction
            
        Returns:
            ProcessingResult
        """
        warnings = []
        
        # Stage 1: Text Segmentation
        self._update_progress(
            ProcessingStage.TEXT_SEGMENTATION,
            0.3,
            current_item="Segmenting text"
        )
        
        try:
            segments = dividir_texto_en_fragmentos(content)
            if not segments:
                raise ValueError("Text segmentation produced no segments")
            
            self.logger.info(f"Text segmented into {len(segments)} parts")
            
        except Exception as e:
            raise RuntimeError(f"Text segmentation failed: {str(e)}")
        
        # Stage 2: Flashcard Generation
        self._update_progress(
            ProcessingStage.FLASHCARD_GENERATION,
            0.4,
            current_item="Generating flashcards",
            total_items=len(segments),
            processed_items=0
        )
        
        all_flashcards = []
        total_segments = len(segments)
        
        for i, (segment_text, tokens) in enumerate(segments):
            if self.should_cancel:
                raise RuntimeError("Processing cancelled by user")
            
            try:
                # Calculate flashcard count for this segment
                num_flashcards = salida_flashcards(tokens)
                
                # Generate flashcards
                flashcards, metadatos = generar_flashcards_parametrizadas(segment_text, num_flashcards)
                all_flashcards.append(flashcards)
                
                # Update progress
                segment_progress = 0.4 + ((i + 1) / total_segments) * 0.4  # 40-80% for generation
                self._update_progress(
                    ProcessingStage.FLASHCARD_GENERATION,
                    segment_progress,
                    current_item=f"Generated flashcards for segment {i + 1}/{total_segments}",
                    total_items=total_segments,
                    processed_items=i + 1
                )
                
                # API delay between segments (except for last segment)
                if i < total_segments - 1:
                    time.sleep(self.api_delay)
                
            except Exception as e:
                self.logger.error(f"Error generating flashcards for segment {i + 1}: {e}")
                warnings.append(f"Failed to generate flashcards for segment {i + 1}: {str(e)}")
        
        if not all_flashcards:
            raise RuntimeError("No flashcards were generated")
        
        # Combine all flashcards
        total_flashcards = "\n".join(all_flashcards)
        flashcard_count = len([line for line in total_flashcards.split('\n') if '\t' in line])
        
        # Stage 3: Anki Import
        self._update_progress(
            ProcessingStage.ANKI_IMPORT,
            0.8,
            current_item="Importing to Anki"
        )
        
        try:
            import_result = procesar_importacion_automática(total_flashcards)
            
            # Extract deck name from import result if available
            deck_name = None
            if hasattr(import_result, 'get'):
                deck_name = import_result.get('deck_name')
            
        except Exception as e:
            raise RuntimeError(f"Anki import failed: {str(e)}")
        
        # Create successful result
        return ProcessingResult(
            success=True,
            input_mode=input_mode,
            source_info=source_info,
            flashcard_count=flashcard_count,
            segment_count=len(segments),
            processing_time=0,  # Will be set by caller
            deck_name=deck_name,
            warnings=warnings,
            metadata={
                "extraction_metadata": extraction_metadata,
                "total_tokens": sum(tokens for _, tokens in segments),
                "api_delay": self.api_delay
            }
        )
    
    def _map_input_to_extraction_mode(self, input_mode: InputMode) -> ExtractionMode:
        """
        Map InputMode to ExtractionMode.
        
        Args:
            input_mode: Input mode from UI
            
        Returns:
            Corresponding ExtractionMode
        """
        mode_map = {
            InputMode.PDF_ANNOTATIONS: ExtractionMode.PDF_ANNOTATIONS,
            InputMode.PDF_FULLTEXT: ExtractionMode.PDF_FULLTEXT,
            InputMode.DIRECT_TEXT: ExtractionMode.DIRECT_TEXT
        }
        
        if input_mode not in mode_map:
            raise ValueError(f"Cannot map input mode {input_mode} to extraction mode")
        
        return mode_map[input_mode]
    
    def cancel_processing(self):
        """Cancel current processing operation."""
        self.should_cancel = True
        self.logger.info("Processing cancellation requested")
    
    def is_processing_active(self) -> bool:
        """Check if processing is currently active."""
        return self.is_processing
    
    def get_current_state(self) -> Optional[ProcessingState]:
        """Get current processing state."""
        return self.current_state


class ProcessingPipelineIntegration:
    """
    Integration layer that connects the unified processor with the existing GUI
    and provides backward compatibility with existing interfaces.
    """
    
    def __init__(self):
        """Initialize the integration layer."""
        self.processor = UnifiedContentProcessor()
        self.logger = logging.getLogger(__name__)
    
    def process_like_acumular_flashcards(self, source: str, modo: str = "con") -> str:
        """
        Process content using the same interface as acumular_total_flashacards.
        
        This method provides backward compatibility with existing GUI code.
        
        Args:
            source: File path or text content
            modo: Processing mode ("con" for annotations, "sin" for full text)
            
        Returns:
            Combined flashcards text ready for import
        """
        # Determine input mode based on source and modo
        if source.endswith('.pdf'):
            input_mode = InputMode.PDF_ANNOTATIONS if modo == "con" else InputMode.PDF_FULLTEXT
        else:
            # Assume direct text input
            input_mode = InputMode.DIRECT_TEXT
        
        # Process through unified pipeline
        result = self.processor.process_content(input_mode, source)
        
        if result.success:
            return result.metadata.get("flashcards_text", "")
        else:
            raise RuntimeError(f"Processing failed: {result.error}")
    
    def process_with_progress_reporting(
        self,
        input_mode: InputMode,
        source: Any,
        progress_callback: Callable[[ProcessingState], None],
        options: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process content with progress reporting.
        
        Args:
            input_mode: Type of input being processed
            source: Content source
            progress_callback: Function to call with progress updates
            options: Additional processing options
            
        Returns:
            ProcessingResult
        """
        # Register progress callback
        self.processor.register_progress_callback(progress_callback)
        
        try:
            return self.processor.process_content(input_mode, source, options)
        finally:
            # Remove callback to prevent memory leaks
            if progress_callback in self.processor.progress_callbacks:
                self.processor.progress_callbacks.remove(progress_callback)
    
    def validate_input_for_mode(self, input_mode: InputMode, source: Any) -> Tuple[bool, str]:
        """
        Validate input for the specified mode.
        
        Args:
            input_mode: Input mode to validate for
            source: Input source to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if input_mode == InputMode.DIRECT_TEXT:
                if not isinstance(source, str) or not source.strip():
                    return False, "Direct text input cannot be empty"
                
                # Use direct text integration for validation
                is_valid, error = self.processor.direct_text_integration.validate_input(source)
                return is_valid, error or ""
            
            elif input_mode in [InputMode.PDF_ANNOTATIONS, InputMode.PDF_FULLTEXT]:
                if isinstance(source, list):
                    # Multiple files
                    if not source:
                        return False, "No files provided"
                    
                    for file_path in source:
                        if not isinstance(file_path, str) or not file_path.endswith('.pdf'):
                            return False, f"Invalid PDF file: {file_path}"
                        
                        extraction_mode = self.processor._map_input_to_extraction_mode(input_mode)
                        extractor = self.processor.content_extractor.get_extractor(extraction_mode)
                        if not extractor.validate_source(file_path):
                            return False, f"Cannot access PDF file: {file_path}"
                
                else:
                    # Single file
                    if not isinstance(source, str) or not source.endswith('.pdf'):
                        return False, "Invalid PDF file path"
                    
                    extraction_mode = self.processor._map_input_to_extraction_mode(input_mode)
                    extractor = self.processor.content_extractor.get_extractor(extraction_mode)
                    if not extractor.validate_source(source):
                        return False, f"Cannot access PDF file: {source}"
            
            else:
                return False, f"Unsupported input mode: {input_mode}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def get_processor(self) -> UnifiedContentProcessor:
        """Get the underlying processor instance."""
        return self.processor


# Global instance for backward compatibility
_global_integration = ProcessingPipelineIntegration()


def process_content_unified(input_mode: InputMode, source: Any, **kwargs) -> ProcessingResult:
    """
    Global function for unified content processing.
    
    Args:
        input_mode: Type of input being processed
        source: Content source
        **kwargs: Additional options
        
    Returns:
        ProcessingResult
    """
    return _global_integration.processor.process_content(input_mode, source, kwargs)


def get_global_processor() -> UnifiedContentProcessor:
    """Get the global processor instance."""
    return _global_integration.processor


if __name__ == "__main__":
    # Demo usage
    import logging
    logging.basicConfig(level=logging.INFO)
    
    def demo_progress_callback(state: ProcessingState):
        print(f"Progress: {state.stage.value} - {state.progress:.1%} - {state.current_item or 'Processing...'}")
        if state.error:
            print(f"Error: {state.error}")
    
    # Create integration
    integration = ProcessingPipelineIntegration()
    
    # Demo text
    demo_text = """
    Artificial intelligence (AI) is intelligence demonstrated by machines, 
    in contrast to the natural intelligence displayed by humans and animals. 
    Leading AI textbooks define the field as the study of "intelligent agents": 
    any device that perceives its environment and takes actions that maximize 
    its chance of successfully achieving its goals.
    """
    
    print("Testing unified content processing...")
    
    # Test validation
    is_valid, error = integration.validate_input_for_mode(InputMode.DIRECT_TEXT, demo_text)
    print(f"Validation: {'PASS' if is_valid else 'FAIL'} - {error}")
    
    if is_valid:
        # Test processing
        result = integration.process_with_progress_reporting(
            InputMode.DIRECT_TEXT,
            demo_text,
            demo_progress_callback
        )
        
        if result.success:
            print(f"\nSUCCESS!")
            print(f"Generated {result.flashcard_count} flashcards")
            print(f"Processing time: {result.processing_time:.2f} seconds")
        else:
            print(f"\nFAILED: {result.error}")