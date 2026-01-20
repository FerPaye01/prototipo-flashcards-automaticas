"""
Direct Text Processing Workflow

This module provides processing pipeline for direct text input that bypasses
file extraction and integrates with the existing flashcard generation system.
"""

import time
from typing import List, Tuple, Dict, Any, Optional
from segmentar_entrada_variable import dividir_texto_en_fragmentos
from generar_flashcards import generar_flashcards_parametrizadas
from logica_limites_flashcards import salida_flashcards
from automatizar_importacion import procesar_importacion_automática
import re


class DirectTextProcessor:
    """
    Processor for direct text input that integrates with existing flashcard workflow.
    
    Provides:
    - Text validation and preprocessing
    - Integration with existing segmentation and generation pipeline
    - Processing state management
    - Error handling and recovery
    """
    
    def __init__(self):
        """Initialize the direct text processor."""
        self.processing_state = {
            'is_processing': False,
            'current_step': None,
            'progress': 0,
            'total_steps': 0,
            'error': None
        }
        
        # Processing configuration
        self.min_text_length = 10
        self.max_text_length = 50000
        self.processing_delay = 60  # Delay between API calls (same as original)
    
    def validate_text_input(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate direct text input for processing.
        
        Args:
            text: Input text to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "Text cannot be empty"
        
        text = text.strip()
        
        if len(text) < self.min_text_length:
            return False, f"Text must be at least {self.min_text_length} characters"
        
        if len(text) > self.max_text_length:
            return False, f"Text cannot exceed {self.max_text_length} characters"
        
        # Check for reasonable content (not just whitespace/special chars)
        word_count = len(text.split())
        if word_count < 3:
            return False, "Text must contain at least 3 words"
        
        # Check for reasonable character distribution
        alpha_chars = sum(1 for c in text if c.isalpha())
        if alpha_chars / len(text) < 0.3:
            return False, "Text must contain sufficient alphabetic content"
        
        return True, None
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess direct text input for optimal segmentation.
        
        Args:
            text: Raw input text
            
        Returns:
            Preprocessed text ready for segmentation
        """
        # Basic cleanup
        text = text.strip()
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive whitespace while preserving paragraph structure
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
        text = re.sub(r'\n{3,}', '\n\n', text)  # Multiple newlines to double newline
        
        # Ensure proper sentence endings for better segmentation
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
        
        # Clean up common formatting artifacts
        text = re.sub(r'^\s*[-•*]\s*', '• ', text, flags=re.MULTILINE)  # Normalize bullets
        
        return text
    
    def process_direct_text(self, text: str, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Process direct text input through the complete flashcard generation pipeline.
        
        Args:
            text: Input text to process
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with processing results
        """
        try:
            self.processing_state = {
                'is_processing': True,
                'current_step': 'validation',
                'progress': 0,
                'total_steps': 5,
                'error': None
            }
            
            if progress_callback:
                progress_callback(self.processing_state)
            
            # Step 1: Validate input
            is_valid, error_msg = self.validate_text_input(text)
            if not is_valid:
                raise ValueError(f"Input validation failed: {error_msg}")
            
            self.processing_state.update({
                'current_step': 'preprocessing',
                'progress': 1
            })
            if progress_callback:
                progress_callback(self.processing_state)
            
            # Step 2: Preprocess text
            processed_text = self.preprocess_text(text)
            
            self.processing_state.update({
                'current_step': 'segmentation',
                'progress': 2
            })
            if progress_callback:
                progress_callback(self.processing_state)
            
            # Step 3: Segment text using existing logic
            segments = dividir_texto_en_fragmentos(processed_text)
            
            self.processing_state.update({
                'current_step': 'generation',
                'progress': 3
            })
            if progress_callback:
                progress_callback(self.processing_state)
            
            # Step 4: Generate flashcards for each segment
            all_flashcards = []
            total_segments = len(segments)
            
            for i, (segment_text, tokens) in enumerate(segments, 1):
                # Calculate number of flashcards for this segment
                num_flashcards = salida_flashcards(tokens)
                
                # Generate flashcards
                flashcards, metadatos = generar_flashcards_parametrizadas(segment_text, num_flashcards)
                all_flashcards.append(flashcards)
                
                # Update progress within generation step
                segment_progress = 3 + (i / total_segments) * 0.8  # 80% of step 4
                self.processing_state.update({
                    'progress': segment_progress,
                    'current_step': f'generation (segment {i}/{total_segments})'
                })
                if progress_callback:
                    progress_callback(self.processing_state)
                
                # Delay between API calls (same as original logic)
                if i < total_segments:  # Don't delay after last segment
                    time.sleep(self.processing_delay)
            
            # Combine all flashcards
            total_flashcards = "\n".join(all_flashcards)
            
            self.processing_state.update({
                'current_step': 'import',
                'progress': 4
            })
            if progress_callback:
                progress_callback(self.processing_state)
            
            # Step 5: Import to Anki
            import_result = procesar_importacion_automática(total_flashcards)
            
            # Calculate final statistics
            flashcard_count = len([line for line in total_flashcards.split('\n') if '\t' in line])
            
            result = {
                'success': True,
                'flashcards_text': total_flashcards,
                'flashcard_count': flashcard_count,
                'segment_count': len(segments),
                'total_tokens': sum(tokens for _, tokens in segments),
                'import_result': import_result,
                'processing_time': None  # Will be set by caller
            }
            
            self.processing_state.update({
                'current_step': 'completed',
                'progress': 5,
                'is_processing': False
            })
            if progress_callback:
                progress_callback(self.processing_state)
            
            return result
            
        except Exception as e:
            self.processing_state.update({
                'is_processing': False,
                'error': str(e)
            })
            if progress_callback:
                progress_callback(self.processing_state)
            
            return {
                'success': False,
                'error': str(e),
                'flashcards_text': None,
                'flashcard_count': 0,
                'segment_count': 0,
                'total_tokens': 0,
                'import_result': None,
                'processing_time': None
            }
    
    def get_processing_state(self) -> Dict[str, Any]:
        """
        Get current processing state.
        
        Returns:
            Current processing state dictionary
        """
        return self.processing_state.copy()
    
    def is_processing(self) -> bool:
        """
        Check if processing is currently in progress.
        
        Returns:
            True if processing is active
        """
        return self.processing_state.get('is_processing', False)
    
    def cancel_processing(self):
        """Cancel current processing operation."""
        if self.processing_state.get('is_processing'):
            self.processing_state.update({
                'is_processing': False,
                'current_step': 'cancelled',
                'error': 'Processing cancelled by user'
            })


class DirectTextIntegration:
    """
    Integration class that connects direct text processing with the existing
    flashcard system and provides a unified interface.
    """
    
    def __init__(self):
        """Initialize the integration."""
        self.processor = DirectTextProcessor()
    
    def process_text_like_pdf(self, text: str, modo: str = "sin") -> str:
        """
        Process direct text input using the same interface as PDF processing.
        
        This method mimics the signature of acumular_total_flashacards to provide
        seamless integration with existing GUI code.
        
        Args:
            text: Direct text input
            modo: Processing mode (kept for compatibility, not used for direct text)
            
        Returns:
            Combined flashcards text ready for import
        """
        result = self.processor.process_direct_text(text)
        
        if result['success']:
            return result['flashcards_text']
        else:
            raise RuntimeError(f"Direct text processing failed: {result['error']}")
    
    def process_with_progress(self, text: str, progress_callback: callable) -> Dict[str, Any]:
        """
        Process direct text with progress reporting.
        
        Args:
            text: Input text
            progress_callback: Function to call with progress updates
            
        Returns:
            Processing result dictionary
        """
        start_time = time.time()
        result = self.processor.process_direct_text(text, progress_callback)
        result['processing_time'] = time.time() - start_time
        return result
    
    def validate_input(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate text input.
        
        Args:
            text: Text to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.processor.validate_text_input(text)
    
    def get_processing_state(self) -> Dict[str, Any]:
        """Get current processing state."""
        return self.processor.get_processing_state()
    
    def is_processing(self) -> bool:
        """Check if processing is active."""
        return self.processor.is_processing()
    
    def cancel_processing(self):
        """Cancel current processing."""
        self.processor.cancel_processing()


# Demo/Test functions
def _demo_progress_callback(state: Dict[str, Any]):
    """Demo progress callback for testing."""
    if state.get('error'):
        print(f"ERROR: {state['error']}")
    else:
        progress = state.get('progress', 0)
        total = state.get('total_steps', 5)
        step = state.get('current_step', 'unknown')
        print(f"Progress: {progress}/{total} - {step}")


if __name__ == "__main__":
    # Demo usage
    integration = DirectTextIntegration()
    
    # Sample text for testing
    sample_text = """
    Machine learning is a subset of artificial intelligence that focuses on algorithms 
    that can learn from data. It involves training models on datasets to make predictions 
    or decisions without being explicitly programmed for every scenario.
    
    There are three main types of machine learning: supervised learning, unsupervised 
    learning, and reinforcement learning. Each type has different applications and 
    methodologies for solving problems.
    
    Supervised learning uses labeled data to train models. The algorithm learns from 
    input-output pairs to make predictions on new, unseen data. Common examples include 
    classification and regression tasks.
    """
    
    print("Testing direct text processing...")
    
    # Test validation
    is_valid, error = integration.validate_input(sample_text)
    print(f"Validation: {'PASS' if is_valid else 'FAIL'} - {error or 'OK'}")
    
    if is_valid:
        # Test processing with progress
        print("\nProcessing text...")
        result = integration.process_with_progress(sample_text, _demo_progress_callback)
        
        if result['success']:
            print(f"\nSUCCESS!")
            print(f"Generated {result['flashcard_count']} flashcards")
            print(f"Processed {result['segment_count']} segments")
            print(f"Total tokens: {result['total_tokens']}")
            print(f"Processing time: {result['processing_time']:.2f} seconds")
        else:
            print(f"\nFAILED: {result['error']}")