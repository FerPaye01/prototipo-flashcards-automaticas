import sys
import os
from unittest.mock import MagicMock, patch
import time

# Mock external dependencies
sys.modules['audio_extract'] = MagicMock()
sys.modules['imageio'] = MagicMock()
sys.modules['playsound'] = MagicMock()

from video_processor import VideoProcessor
from gemini_flashcard_generator import GeminiFlashcardGenerator

def test_video_processor_reconnection():
    print("Testing VideoProcessor reconnection logic...")
    processor = VideoProcessor()
    
    # We want to mock _check_internet_connection to return False twice, then True
    mock_check = MagicMock(side_effect=[False, False, True])
    processor._check_internet_connection = mock_check
    
    # Patch time.sleep to avoid actual delays in the test
    with patch('time.sleep', return_value=None) as mock_sleep:
        processor._wait_for_connection(reason="test connection drop")
        
    assert mock_check.call_count == 3
    assert mock_sleep.call_count == 1
    print("✅ VideoProcessor reconnection logic successfully waited and resumed when online.")

def test_generator_reconnection():
    print("Testing GeminiFlashcardGenerator reconnection logic...")
    generator = GeminiFlashcardGenerator()
    
    mock_check = MagicMock(side_effect=[False, False, True])
    generator._check_internet_connection = mock_check
    
    with patch('time.sleep', return_value=None) as mock_sleep:
        generator._wait_for_connection(reason="test generator connection drop")
        
    assert mock_check.call_count == 3
    assert mock_sleep.call_count == 1
    print("✅ GeminiFlashcardGenerator reconnection logic successfully waited and resumed when online.")

if __name__ == "__main__":
    import traceback
    try:
        test_video_processor_reconnection()
        test_generator_reconnection()
        print("\nAll reconnection tests passed successfully!")
    except Exception as e:
        print("\n❌ Test failed:")
        traceback.print_exc()
        sys.exit(1)
