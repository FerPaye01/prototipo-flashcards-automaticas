# archivo: robust_token_counter.py
"""
Robust token counting module with API fallback and local estimation.
Implements caching and error handling for reliable token calculations.
"""

import time
import logging
from typing import Dict, Optional, Tuple
from functools import lru_cache
import hashlib
import re
from crear_cliente import client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenCounterError(Exception):
    """Custom exception for token counting errors"""
    pass

class RobustTokenCounter:
    """
    Robust token counter with API fallback and local estimation capabilities.
    Implements caching, rate limiting, and comprehensive error handling.
    """
    
    def __init__(self, model: str = "gemini-2.5-pro", cache_size: int = 1000):
        self.model = model
        self.cache_size = cache_size
        self.api_call_count = 0
        self.last_api_call = 0
        self.rate_limit_delay = 1.0  # seconds between API calls
        self.max_retries = 3
        self.retry_delay = 2.0  # seconds
        
        # Statistics for monitoring
        self.stats = {
            'api_calls': 0,
            'cache_hits': 0,
            'fallback_uses': 0,
            'errors': 0
        }
    
    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for text to use as cache key"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _estimate_tokens_locally(self, text: str) -> int:
        """
        Local token estimation fallback using heuristics.
        Based on OpenAI's approximation: ~4 characters per token for English text.
        """
        if not text or not text.strip():
            return 0
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Basic heuristic: 4 characters per token, adjusted for different content types
        char_count = len(text)
        
        # Adjust for different content characteristics
        word_count = len(text.split())
        
        # More accurate estimation considering:
        # - Punctuation and special characters (fewer tokens)
        # - Long words (more characters per token)
        # - Short words (fewer characters per token)
        
        if word_count == 0:
            return max(1, char_count // 4)
        
        avg_word_length = char_count / word_count
        
        # Adjust token estimation based on average word length
        if avg_word_length > 6:  # Longer words, more chars per token
            chars_per_token = 4.5
        elif avg_word_length < 3:  # Shorter words, fewer chars per token
            chars_per_token = 3.0
        else:
            chars_per_token = 4.0
        
        estimated_tokens = max(1, int(char_count / chars_per_token))
        
        logger.debug(f"Local estimation: {char_count} chars, {word_count} words, "
                    f"avg_word_len={avg_word_length:.1f}, estimated={estimated_tokens} tokens")
        
        return estimated_tokens
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting between API calls"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_call
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_api_call = time.time()
    
    @lru_cache(maxsize=1000)
    def _cached_api_count(self, text_hash: str, text: str) -> int:
        """Cached API token counting with error handling and retries"""
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()
                
                logger.debug(f"API call attempt {attempt + 1} for text hash: {text_hash[:8]}...")
                
                response = client.models.count_tokens(model=self.model, contents=text)
                token_count = response.total_tokens
                
                self.stats['api_calls'] += 1
                self.api_call_count += 1
                
                logger.debug(f"API returned {token_count} tokens for text hash: {text_hash[:8]}...")
                
                return token_count
                
            except Exception as e:
                logger.warning(f"API call attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    sleep_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All API attempts failed for text hash: {text_hash[:8]}...")
                    raise TokenCounterError(f"API token counting failed after {self.max_retries} attempts: {str(e)}")
    
    def count_tokens(self, text: str, use_fallback: bool = True) -> Tuple[int, str]:
        """
        Count tokens with fallback mechanisms.
        
        Args:
            text: Text to count tokens for
            use_fallback: Whether to use local estimation if API fails
            
        Returns:
            Tuple of (token_count, method_used)
            method_used can be: 'api', 'cache', 'fallback'
        """
        if not text or not text.strip():
            return 0, 'direct'
        
        text_hash = self._get_text_hash(text)
        
        # Check if we already have this in cache
        try:
            # Try to get from cache first
            if hasattr(self._cached_api_count, 'cache_info'):
                cache_info = self._cached_api_count.cache_info()
                if text_hash in [str(hash(key)) for key in self._cached_api_count.__wrapped__.__code__.co_names]:
                    self.stats['cache_hits'] += 1
                    return self._cached_api_count(text_hash, text), 'cache'
        except:
            pass
        
        # Try API call
        try:
            token_count = self._cached_api_count(text_hash, text)
            return token_count, 'api'
            
        except TokenCounterError as e:
            self.stats['errors'] += 1
            
            if use_fallback:
                logger.warning(f"API failed, using local estimation: {str(e)}")
                self.stats['fallback_uses'] += 1
                estimated_count = self._estimate_tokens_locally(text)
                return estimated_count, 'fallback'
            else:
                raise e
    
    def count_tokens_safe(self, text: str) -> int:
        """
        Safe token counting that always returns a result.
        Uses fallback estimation if API fails.
        """
        try:
            count, method = self.count_tokens(text, use_fallback=True)
            return count
        except Exception as e:
            logger.error(f"All token counting methods failed: {str(e)}")
            # Last resort: very basic estimation
            return max(1, len(text.split()) // 2)
    
    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics"""
        return self.stats.copy()
    
    def clear_cache(self):
        """Clear the token counting cache"""
        self._cached_api_count.cache_clear()
        logger.info("Token counting cache cleared")
    
    def get_cache_info(self):
        """Get cache information"""
        return self._cached_api_count.cache_info()

# Global instance for backward compatibility
_global_counter = RobustTokenCounter()

def contar_tokens(texto: str, modelo: str = "gemini-2.5-pro") -> int:
    """
    Backward compatible function that uses the robust token counter.
    Maintains the same interface as the original contar_tokens function.
    """
    global _global_counter
    
    # Update model if different
    if _global_counter.model != modelo:
        _global_counter = RobustTokenCounter(model=modelo)
    
    return _global_counter.count_tokens_safe(texto)

def contar_tokens_with_info(texto: str, modelo: str = "gemini-2.5-pro") -> Tuple[int, str]:
    """
    Enhanced function that returns both token count and method used.
    """
    global _global_counter
    
    # Update model if different
    if _global_counter.model != modelo:
        _global_counter = RobustTokenCounter(model=modelo)
    
    return _global_counter.count_tokens(texto, use_fallback=True)

def get_token_counter_stats() -> Dict[str, int]:
    """Get statistics from the global token counter"""
    return _global_counter.get_stats()

def clear_token_cache():
    """Clear the global token counter cache"""
    _global_counter.clear_cache()

# For testing and debugging
if __name__ == "__main__":
    # Test the robust token counter
    counter = RobustTokenCounter()
    
    test_texts = [
        "Hello world",
        "This is a longer text that should have more tokens for testing purposes.",
        "Short",
        "",
        "A" * 1000,  # Very long text
    ]
    
    for text in test_texts:
        try:
            count, method = counter.count_tokens(text)
            print(f"Text: '{text[:50]}...' -> {count} tokens (method: {method})")
        except Exception as e:
            print(f"Error counting tokens for '{text[:50]}...': {e}")
    
    print(f"\nStats: {counter.get_stats()}")
    print(f"Cache info: {counter.get_cache_info()}")