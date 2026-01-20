# archivo: enhanced_segmentation_system.py
"""
Enhanced segmentation system that integrates robust token counting and improved text segmentation.
Provides comprehensive logging, debugging capabilities, and circuit breakers to prevent infinite loops.
"""

import logging
import time
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from robust_token_counter import RobustTokenCounter, contar_tokens
from improved_text_segmenter import ImprovedTextSegmenter, SegmentationResult
from logica_limites_tokens import limite_tokens_input

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SystemStats:
    """Comprehensive system statistics"""
    token_counter_stats: Dict[str, int]
    segmenter_stats: Dict[str, Any]
    total_texts_processed: int
    total_segments_created: int
    total_processing_time: float
    average_processing_time: float
    errors_encountered: int

class EnhancedSegmentationSystem:
    """
    Unified system that combines robust token counting and improved text segmentation.
    Provides comprehensive logging, debugging, and monitoring capabilities.
    """
    
    def __init__(self, 
                 max_tokens: int = None,
                 model: str = "gemini-2.5-pro",
                 safety_margin: int = 50,
                 enable_debug_logging: bool = False,
                 log_file: Optional[str] = None):
        """
        Initialize the enhanced segmentation system.
        
        Args:
            max_tokens: Maximum tokens per segment
            model: AI model to use for token counting
            safety_margin: Safety margin for token calculations
            enable_debug_logging: Enable detailed debug logging
            log_file: Optional log file path
        """
        self.max_tokens = max_tokens or limite_tokens_input
        self.model = model
        self.safety_margin = safety_margin
        
        # Configure logging
        if enable_debug_logging:
            logging.getLogger().setLevel(logging.DEBUG)
        
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logging.getLogger().addHandler(file_handler)
        
        # Initialize components
        self.token_counter = RobustTokenCounter(model=model)
        self.segmenter = ImprovedTextSegmenter(
            max_tokens=self.max_tokens,
            token_counter_func=self.token_counter.count_tokens_safe,
            safety_margin=safety_margin
        )
        
        # System statistics
        self.system_stats = {
            'texts_processed': 0,
            'total_processing_time': 0.0,
            'errors_encountered': 0,
            'sessions': []
        }
        
        logger.info(f"Enhanced Segmentation System initialized with max_tokens={self.max_tokens}, model={model}")
    
    def process_text(self, text: str, session_id: Optional[str] = None) -> SegmentationResult:
        """
        Process text with comprehensive logging and error handling.
        
        Args:
            text: Input text to process
            session_id: Optional session identifier for tracking
            
        Returns:
            SegmentationResult with segments and metadata
        """
        start_time = time.time()
        session_id = session_id or f"session_{int(start_time)}"
        
        logger.info(f"Starting text processing - Session: {session_id}")
        logger.debug(f"Input text length: {len(text)} characters")
        
        try:
            # Validate input
            if not text or not text.strip():
                logger.warning("Empty or whitespace-only text provided")
                return SegmentationResult(
                    segments=[],
                    total_tokens=0,
                    segmentation_method="empty_input",
                    warnings=["Input text is empty or contains only whitespace"],
                    original_length=0,
                    processed_length=0
                )
            
            # Pre-processing validation
            logger.debug("Performing pre-processing validation")
            
            # Check if text is extremely long
            if len(text) > 1000000:  # 1MB of text
                logger.warning(f"Very large text detected: {len(text)} characters")
            
            # Perform segmentation
            logger.debug("Starting text segmentation")
            result = self.segmenter.segment_text(text)
            
            # Post-processing validation
            self._validate_result(result, text)
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_stats(result, processing_time, session_id)
            
            logger.info(f"Text processing completed - Session: {session_id}, "
                       f"Segments: {len(result.segments)}, "
                       f"Total tokens: {result.total_tokens}, "
                       f"Time: {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.system_stats['errors_encountered'] += 1
            
            logger.error(f"Error processing text - Session: {session_id}, "
                        f"Error: {str(e)}, Time: {processing_time:.2f}s")
            
            # Return error result
            return SegmentationResult(
                segments=[],
                total_tokens=0,
                segmentation_method="error",
                warnings=[f"Processing failed: {str(e)}"],
                original_length=len(text) if text else 0,
                processed_length=0
            )
    
    def _validate_result(self, result: SegmentationResult, original_text: str):
        """
        Validate segmentation result and add additional warnings if needed.
        """
        # Check for critical issues
        if not result.segments and original_text.strip():
            result.warnings.append("No segments created from non-empty input")
        
        # Check token distribution
        if result.segments:
            token_counts = [tokens for _, tokens in result.segments]
            max_tokens = max(token_counts)
            min_tokens = min(token_counts)
            avg_tokens = sum(token_counts) / len(token_counts)
            
            if max_tokens > self.max_tokens:
                result.warnings.append(f"Segment exceeds token limit: {max_tokens} > {self.max_tokens}")
            
            if min_tokens < 10 and len(result.segments) > 1:
                result.warnings.append(f"Very small segment detected: {min_tokens} tokens")
            
            # Check for extreme imbalance
            if max_tokens > avg_tokens * 3:
                result.warnings.append("Significant token imbalance between segments")
        
        # Log warnings
        for warning in result.warnings:
            logger.warning(f"Validation warning: {warning}")
    
    def _update_stats(self, result: SegmentationResult, processing_time: float, session_id: str):
        """Update system statistics"""
        self.system_stats['texts_processed'] += 1
        self.system_stats['total_processing_time'] += processing_time
        
        # Record session details
        session_data = {
            'session_id': session_id,
            'segments_count': len(result.segments),
            'total_tokens': result.total_tokens,
            'processing_time': processing_time,
            'method_used': result.segmentation_method,
            'warnings_count': len(result.warnings),
            'timestamp': time.time()
        }
        
        self.system_stats['sessions'].append(session_data)
        
        # Keep only last 100 sessions to prevent memory bloat
        if len(self.system_stats['sessions']) > 100:
            self.system_stats['sessions'] = self.system_stats['sessions'][-100:]
    
    def get_comprehensive_stats(self) -> SystemStats:
        """
        Get comprehensive system statistics.
        
        Returns:
            SystemStats object with all system metrics
        """
        token_stats = self.token_counter.get_stats()
        segmenter_stats = self.segmenter.get_stats()
        
        avg_processing_time = 0.0
        if self.system_stats['texts_processed'] > 0:
            avg_processing_time = (
                self.system_stats['total_processing_time'] / 
                self.system_stats['texts_processed']
            )
        
        total_segments = sum(
            session['segments_count'] 
            for session in self.system_stats['sessions']
        )
        
        return SystemStats(
            token_counter_stats=token_stats,
            segmenter_stats=segmenter_stats,
            total_texts_processed=self.system_stats['texts_processed'],
            total_segments_created=total_segments,
            total_processing_time=self.system_stats['total_processing_time'],
            average_processing_time=avg_processing_time,
            errors_encountered=self.system_stats['errors_encountered']
        )
    
    def export_stats(self, file_path: str):
        """Export statistics to JSON file"""
        stats = self.get_comprehensive_stats()
        stats_dict = asdict(stats)
        
        # Add session details
        stats_dict['recent_sessions'] = self.system_stats['sessions'][-10:]  # Last 10 sessions
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stats_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Statistics exported to {file_path}")
    
    def clear_caches(self):
        """Clear all caches and reset statistics"""
        self.token_counter.clear_cache()
        
        # Reset statistics
        self.system_stats = {
            'texts_processed': 0,
            'total_processing_time': 0.0,
            'errors_encountered': 0,
            'sessions': []
        }
        
        logger.info("Caches cleared and statistics reset")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform system health check.
        
        Returns:
            Dictionary with health status information
        """
        health_status = {
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test token counter
            test_count, method = self.token_counter.count_tokens("Test text for health check")
            if method == 'fallback':
                health_status['issues'].append("Token counter using fallback method")
                health_status['recommendations'].append("Check API connectivity")
            
            # Check error rate
            if self.system_stats['texts_processed'] > 0:
                error_rate = self.system_stats['errors_encountered'] / self.system_stats['texts_processed']
                if error_rate > 0.1:  # More than 10% error rate
                    health_status['issues'].append(f"High error rate: {error_rate:.1%}")
                    health_status['status'] = 'degraded'
            
            # Check cache performance
            cache_info = self.token_counter.get_cache_info()
            if hasattr(cache_info, 'hit_rate') and cache_info.hit_rate < 0.5:
                health_status['recommendations'].append("Consider increasing cache size")
            
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['issues'].append(f"Health check failed: {str(e)}")
        
        return health_status

# Global instance for backward compatibility
_global_system = None

def get_global_system() -> EnhancedSegmentationSystem:
    """Get or create global segmentation system instance"""
    global _global_system
    if _global_system is None:
        _global_system = EnhancedSegmentationSystem()
    return _global_system

def dividir_texto_en_fragmentos_enhanced(texto: str, 
                                       max_tokens: int = None, 
                                       contar_tokens_func=None,
                                       session_id: Optional[str] = None) -> List[Tuple[str, int]]:
    """
    Enhanced version of the original function with comprehensive logging and error handling.
    Maintains backward compatibility while providing improved functionality.
    """
    system = get_global_system()
    
    # Update system configuration if parameters provided
    if max_tokens and max_tokens != system.max_tokens:
        system.max_tokens = max_tokens
        system.segmenter.max_tokens = max_tokens
    
    result = system.process_text(texto, session_id)
    return result.segments

# Backward compatibility - enhanced version of original function
def dividir_texto_en_fragmentos(texto: str, max_tokens: int = None, contar_tokens_func=None) -> List[Tuple[str, int]]:
    """
    Backward compatible function that uses the enhanced system.
    This replaces the original function with improved functionality.
    """
    return dividir_texto_en_fragmentos_enhanced(texto, max_tokens, contar_tokens_func)

# For testing and debugging
if __name__ == "__main__":
    # Test the enhanced system
    system = EnhancedSegmentationSystem(
        max_tokens=200,  # Small limit for testing
        enable_debug_logging=True
    )
    
    test_text = """
    This is a comprehensive test of the enhanced segmentation system. It should handle various types of content gracefully.
    
    The system includes:
    • Robust token counting with fallback mechanisms
    • Multi-level text segmentation strategy
    • Comprehensive logging and debugging
    • Circuit breakers to prevent infinite loops
    • Validation to ensure no content loss
    
    This paragraph contains a very long sentence that should be split appropriately by the segmentation algorithm, and it includes multiple clauses separated by commas, semicolons; and other punctuation marks that should be handled correctly by the boundary detection logic.
    
    Final paragraph for testing.
    """
    
    # Process the text
    result = system.process_text(test_text, "test_session_1")
    
    print("Enhanced Segmentation System Test Results:")
    print(f"Method used: {result.segmentation_method}")
    print(f"Total segments: {len(result.segments)}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Warnings: {result.warnings}")
    
    print("\nSegments:")
    for i, (text, tokens) in enumerate(result.segments, 1):
        print(f"{i}. ({tokens} tokens): {text[:80]}...")
    
    # Show system statistics
    stats = system.get_comprehensive_stats()
    print(f"\nSystem Statistics:")
    print(f"Texts processed: {stats.total_texts_processed}")
    print(f"Total segments created: {stats.total_segments_created}")
    print(f"Average processing time: {stats.average_processing_time:.3f}s")
    print(f"Token counter stats: {stats.token_counter_stats}")
    
    # Health check
    health = system.health_check()
    print(f"\nHealth Status: {health['status']}")
    if health['issues']:
        print(f"Issues: {health['issues']}")
    if health['recommendations']:
        print(f"Recommendations: {health['recommendations']}")