# archivo: improved_text_segmenter.py
"""
Improved text segmentation algorithm with multi-level strategy and robust boundary detection.
Implements comprehensive validation to prevent content duplication or loss.
"""

import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from robust_token_counter import RobustTokenCounter, contar_tokens
from logica_limites_tokens import limite_tokens_input

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SegmentationResult:
    """Result of text segmentation with metadata"""
    segments: List[Tuple[str, int]]
    total_tokens: int
    segmentation_method: str
    warnings: List[str]
    original_length: int
    processed_length: int

class ImprovedTextSegmenter:
    """
    Advanced text segmentation with multi-level strategy and comprehensive validation.
    
    Segmentation Strategy:
    1. Preprocessing: Normalize whitespace, remove duplicates
    2. Primary Split: Split by paragraphs/sections  
    3. Secondary Split: Split by sentences if needed
    4. Tertiary Split: Split by clauses/phrases if needed
    5. Emergency Split: Character-level split with word boundaries
    6. Validation: Ensure no segment exceeds limits and no content loss
    """
    
    def __init__(self, max_tokens: int = None, token_counter_func=None, safety_margin: int = 50):
        self.max_tokens = max_tokens or limite_tokens_input
        self.token_counter = token_counter_func or contar_tokens
        self.safety_margin = safety_margin
        self.max_iterations = 1000  # Circuit breaker for infinite loops
        
        # Use robust token counter if available
        if hasattr(token_counter_func, '__self__') and isinstance(token_counter_func.__self__, RobustTokenCounter):
            self.robust_counter = token_counter_func.__self__
        else:
            self.robust_counter = RobustTokenCounter()
        
        # Statistics
        self.stats = {
            'segments_created': 0,
            'iterations_used': 0,
            'fallback_splits': 0,
            'validation_failures': 0
        }
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent processing.
        """
        if not text:
            return ""
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Convert various bullet points to standard format
        text = re.sub(r'[•◦▪–—\-]{1,}', ' • ', text)
        
        # Normalize multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Normalize multiple spaces but preserve single newlines
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Clean up around bullets
        text = re.sub(r'\s*•\s*', ' • ', text)
        
        return text.strip()
    
    def _remove_immediate_duplicates(self, text: str, min_words: int = 4, max_window: int = 30) -> str:
        """
        Remove immediate duplicate phrases that appear consecutively.
        This fixes common OCR artifacts and copy-paste errors.
        """
        words = text.split()
        if len(words) < min_words * 2:
            return text
        
        result_words = []
        i = 0
        
        while i < len(words):
            found_duplicate = False
            
            # Try different window sizes, largest first
            max_window_size = min(max_window, (len(words) - i) // 2)
            
            for window_size in range(max_window_size, min_words - 1, -1):
                if i + 2 * window_size <= len(words):
                    window1 = words[i:i + window_size]
                    window2 = words[i + window_size:i + 2 * window_size]
                    
                    if window1 == window2:
                        # Found duplicate, skip the second occurrence
                        result_words.extend(window1)
                        i += 2 * window_size
                        found_duplicate = True
                        logger.debug(f"Removed duplicate phrase: {' '.join(window1[:5])}...")
                        break
            
            if not found_duplicate:
                result_words.append(words[i])
                i += 1
        
        return " ".join(result_words)
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraphs and major sections."""
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Further split by bullets if paragraphs are still too long
        result = []
        for para in paragraphs:
            if ' • ' in para:
                # Split by bullets but keep the bullet with the content
                bullet_parts = re.split(r'(\s*•\s*)', para)
                current_part = ""
                
                for i, part in enumerate(bullet_parts):
                    if part.strip() == '•' or part.strip() == ' • ':
                        if current_part.strip():
                            result.append(current_part.strip())
                        current_part = part
                    else:
                        current_part += part
                
                if current_part.strip():
                    result.append(current_part.strip())
            else:
                result.append(para.strip())
        
        return [p for p in result if p.strip()]
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """Split text by sentences using improved regex."""
        # Enhanced sentence splitting that handles common abbreviations
        sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])'
        
        # Don't split on common abbreviations
        text_protected = text
        abbreviations = ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.', 'etc.', 'vs.', 'e.g.', 'i.e.']
        
        for abbr in abbreviations:
            text_protected = text_protected.replace(abbr, abbr.replace('.', '<!DOT!>'))
        
        sentences = re.split(sentence_endings, text_protected)
        
        # Restore dots in abbreviations
        sentences = [s.replace('<!DOT!>', '.').strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _split_by_clauses(self, text: str) -> List[str]:
        """Split text by clauses and phrases."""
        # Split by commas, semicolons, and conjunctions
        clause_pattern = r'(?<=[,;])\s+|(?:\s+(?:and|but|or|however|therefore|moreover|furthermore|nevertheless)\s+)'
        
        clauses = re.split(clause_pattern, text, flags=re.IGNORECASE)
        return [c.strip() for c in clauses if c.strip()]
    
    def _split_by_words(self, text: str, max_words_per_chunk: int = None) -> List[str]:
        """Split text by words, respecting word boundaries."""
        words = text.split()
        
        if not max_words_per_chunk:
            # Estimate words per chunk based on token limit
            # Rough estimate: 1.3 words per token
            max_words_per_chunk = max(10, int(self.max_tokens * 0.75))
        
        chunks = []
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            
            if len(current_chunk) >= max_words_per_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _emergency_character_split(self, text: str) -> List[str]:
        """
        Emergency character-level splitting while trying to preserve word boundaries.
        Used when all other methods fail.
        """
        logger.warning("Using emergency character-level splitting")
        self.stats['fallback_splits'] += 1
        
        # Estimate characters per token (rough approximation)
        chars_per_token = 4
        max_chars = (self.max_tokens - self.safety_margin) * chars_per_token
        
        chunks = []
        current_pos = 0
        
        while current_pos < len(text):
            end_pos = min(current_pos + max_chars, len(text))
            
            # Try to find a word boundary near the end
            if end_pos < len(text):
                # Look backwards for a space
                for i in range(end_pos, max(current_pos, end_pos - 100), -1):
                    if text[i].isspace():
                        end_pos = i
                        break
            
            chunk = text[current_pos:end_pos].strip()
            if chunk:
                chunks.append(chunk)
            
            current_pos = end_pos
            
            # Circuit breaker
            if len(chunks) > self.max_iterations:
                logger.error("Emergency split exceeded maximum iterations")
                break
        
        return chunks
    
    def _calculate_safe_token_limit(self) -> int:
        """Calculate safe token limit with margin for API overhead."""
        return max(50, self.max_tokens - self.safety_margin)
    
    def _validate_segment_tokens(self, segment: str) -> Tuple[bool, int]:
        """
        Validate that a segment doesn't exceed token limits.
        Returns (is_valid, token_count)
        """
        try:
            token_count = self.token_counter(segment)
            safe_limit = self._calculate_safe_token_limit()
            return token_count <= safe_limit, token_count
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            # Fallback to character-based estimation
            estimated_tokens = len(segment) // 4
            safe_limit = self._calculate_safe_token_limit()
            return estimated_tokens <= safe_limit, estimated_tokens
    
    def _split_oversized_segment(self, segment: str, method_name: str) -> List[str]:
        """
        Split a segment that exceeds token limits using progressively more aggressive methods.
        """
        logger.debug(f"Splitting oversized segment using {method_name}")
        
        # Try different splitting methods in order of preference
        methods = [
            ("sentences", self._split_by_sentences),
            ("clauses", self._split_by_clauses),
            ("words", self._split_by_words),
            ("characters", self._emergency_character_split)
        ]
        
        for method_name, method_func in methods:
            try:
                sub_segments = method_func(segment)
                
                # Validate all sub-segments
                valid_segments = []
                for sub_seg in sub_segments:
                    is_valid, token_count = self._validate_segment_tokens(sub_seg)
                    if is_valid:
                        valid_segments.append(sub_seg)
                    else:
                        # Recursively split if still too large
                        if method_name != "characters":
                            valid_segments.extend(self._split_oversized_segment(sub_seg, method_name))
                        else:
                            # Last resort: truncate
                            logger.warning(f"Truncating segment that exceeds limits even after character split")
                            valid_segments.append(sub_seg[:self.max_tokens * 3])  # Rough character limit
                
                if valid_segments:
                    return valid_segments
                    
            except Exception as e:
                logger.error(f"Split method {method_name} failed: {e}")
                continue
        
        # If all methods fail, return original segment (will be caught in validation)
        logger.error("All splitting methods failed")
        return [segment]
    
    def _merge_small_segments(self, segments: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        """
        Merge adjacent small segments to optimize token usage.
        """
        if len(segments) <= 1:
            return segments
        
        merged = []
        current_text = ""
        current_tokens = 0
        safe_limit = self._calculate_safe_token_limit()
        
        for text, tokens in segments:
            # Try to merge with current segment
            if current_text:
                combined_text = current_text + " " + text
                combined_tokens = current_tokens + tokens
                
                # Check if combined segment would exceed limits
                if combined_tokens <= safe_limit:
                    # Verify with actual token count (tokens might not be additive)
                    try:
                        actual_tokens = self.token_counter(combined_text)
                        if actual_tokens <= safe_limit:
                            current_text = combined_text
                            current_tokens = actual_tokens
                            continue
                    except Exception as e:
                        logger.debug(f"Token verification failed during merge: {e}")
            
            # Can't merge, save current and start new
            if current_text:
                merged.append((current_text, current_tokens))
            
            current_text = text
            current_tokens = tokens
        
        # Don't forget the last segment
        if current_text:
            merged.append((current_text, current_tokens))
        
        return merged
    
    def _validate_segmentation_result(self, original_text: str, segments: List[Tuple[str, int]]) -> List[str]:
        """
        Validate segmentation result to ensure no content loss or duplication.
        Returns list of warnings.
        """
        warnings = []
        
        # Check for empty segments
        empty_segments = [i for i, (text, _) in enumerate(segments) if not text.strip()]
        if empty_segments:
            warnings.append(f"Found {len(empty_segments)} empty segments")
        
        # Check total length preservation (approximate)
        original_length = len(original_text.replace(' ', '').replace('\n', ''))
        combined_length = len(''.join(text for text, _ in segments).replace(' ', '').replace('\n', ''))
        
        length_diff_ratio = abs(original_length - combined_length) / max(original_length, 1)
        if length_diff_ratio > 0.1:  # More than 10% difference
            warnings.append(f"Significant length difference: original={original_length}, combined={combined_length}")
        
        # Check for segments exceeding token limits
        safe_limit = self._calculate_safe_token_limit()
        oversized = [(i, tokens) for i, (_, tokens) in enumerate(segments) if tokens > safe_limit]
        if oversized:
            warnings.append(f"Found {len(oversized)} segments exceeding token limit")
        
        # Check for very small segments (might indicate over-segmentation)
        very_small = [(i, tokens) for i, (_, tokens) in enumerate(segments) if tokens < 10]
        if len(very_small) > len(segments) * 0.3:  # More than 30% are very small
            warnings.append(f"Many small segments detected: {len(very_small)}/{len(segments)}")
        
        return warnings
    
    def segment_text(self, text: str) -> SegmentationResult:
        """
        Main segmentation method using multi-level strategy.
        
        Args:
            text: Input text to segment
            
        Returns:
            SegmentationResult with segments and metadata
        """
        if not text or not text.strip():
            return SegmentationResult(
                segments=[],
                total_tokens=0,
                segmentation_method="empty",
                warnings=["Input text is empty"],
                original_length=0,
                processed_length=0
            )
        
        original_length = len(text)
        iteration_count = 0
        
        # Step 1: Preprocessing
        logger.debug("Starting text segmentation - preprocessing")
        normalized_text = self._normalize_text(text)
        deduplicated_text = self._remove_immediate_duplicates(normalized_text)
        
        processed_length = len(deduplicated_text)
        
        # Step 2: Multi-level segmentation
        segmentation_methods = [
            ("paragraphs", self._split_by_paragraphs),
            ("sentences", self._split_by_sentences),
            ("clauses", self._split_by_clauses),
            ("words", self._split_by_words)
        ]
        
        segments = []
        method_used = "direct"
        
        # Try each segmentation method
        for method_name, method_func in segmentation_methods:
            try:
                logger.debug(f"Trying segmentation method: {method_name}")
                
                if not segments:
                    # First method - split the whole text
                    initial_segments = method_func(deduplicated_text)
                else:
                    # Subsequent methods - only split oversized segments
                    initial_segments = []
                    for seg_text, seg_tokens in segments:
                        safe_limit = self._calculate_safe_token_limit()
                        if seg_tokens > safe_limit:
                            initial_segments.extend(method_func(seg_text))
                        else:
                            initial_segments.append(seg_text)
                
                # Validate and calculate tokens for each segment
                validated_segments = []
                needs_further_splitting = False
                
                for segment_text in initial_segments:
                    iteration_count += 1
                    if iteration_count > self.max_iterations:
                        logger.error("Maximum iterations exceeded - circuit breaker activated")
                        break
                    
                    is_valid, token_count = self._validate_segment_tokens(segment_text)
                    
                    if is_valid:
                        validated_segments.append((segment_text, token_count))
                    else:
                        needs_further_splitting = True
                        # Split oversized segment
                        sub_segments = self._split_oversized_segment(segment_text, method_name)
                        for sub_seg in sub_segments:
                            _, sub_tokens = self._validate_segment_tokens(sub_seg)
                            validated_segments.append((sub_seg, sub_tokens))
                
                segments = validated_segments
                method_used = method_name
                
                # If no segments need further splitting, we're done
                if not needs_further_splitting:
                    break
                    
            except Exception as e:
                logger.error(f"Segmentation method {method_name} failed: {e}")
                continue
        
        # Step 3: Post-processing - merge small segments
        if segments:
            segments = self._merge_small_segments(segments)
        
        # Step 4: Final validation
        warnings = self._validate_segmentation_result(text, segments)
        
        # Update statistics
        self.stats['segments_created'] += len(segments)
        self.stats['iterations_used'] += iteration_count
        
        if warnings:
            self.stats['validation_failures'] += 1
        
        # Calculate total tokens
        total_tokens = sum(tokens for _, tokens in segments)
        
        logger.info(f"Segmentation complete: {len(segments)} segments, {total_tokens} total tokens, method: {method_used}")
        
        return SegmentationResult(
            segments=segments,
            total_tokens=total_tokens,
            segmentation_method=method_used,
            warnings=warnings,
            original_length=original_length,
            processed_length=processed_length
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get segmentation statistics"""
        return self.stats.copy()

# Backward compatibility function
def dividir_texto_en_fragmentos(texto: str, max_tokens: int = None, contar_tokens_func=None) -> List[Tuple[str, int]]:
    """
    Backward compatible function that uses the improved segmenter.
    Maintains the same interface as the original function.
    """
    max_tokens = max_tokens or limite_tokens_input
    contar_tokens_func = contar_tokens_func or contar_tokens
    
    segmenter = ImprovedTextSegmenter(max_tokens=max_tokens, token_counter_func=contar_tokens_func)
    result = segmenter.segment_text(texto)
    
    # Log warnings if any
    if result.warnings:
        for warning in result.warnings:
            logger.warning(f"Segmentation warning: {warning}")
    
    return result.segments

# For testing and debugging
if __name__ == "__main__":
    # Test the improved segmenter
    segmenter = ImprovedTextSegmenter(max_tokens=100)  # Small limit for testing
    
    test_text = """
    This is a test document with multiple paragraphs. This paragraph should be split appropriately.
    
    This is another paragraph with some bullets:
    • First bullet point with some content
    • Second bullet point with more content
    • Third bullet point
    
    This is a final paragraph with a very long sentence that might need to be split at the clause level, and it contains multiple clauses separated by commas, and it should be handled gracefully by the segmentation algorithm.
    """
    
    result = segmenter.segment_text(test_text)
    
    print(f"Segmentation Result:")
    print(f"Method used: {result.segmentation_method}")
    print(f"Total segments: {len(result.segments)}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Warnings: {result.warnings}")
    print(f"Original length: {result.original_length}")
    print(f"Processed length: {result.processed_length}")
    
    print("\nSegments:")
    for i, (text, tokens) in enumerate(result.segments, 1):
        print(f"{i}. ({tokens} tokens): {text[:100]}...")
    
    print(f"\nStats: {segmenter.get_stats()}")