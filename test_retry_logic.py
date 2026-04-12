import sys
import os
from unittest.mock import MagicMock, patch
import time

# Mock external dependencies
sys.modules['audio_extract'] = MagicMock()
sys.modules['imageio'] = MagicMock()
sys.modules['playsound'] = MagicMock()

from video_processor import VideoProcessor

def test_retry_logic():
    print("Testing _upload_file_with_retry...")
    
    processor = VideoProcessor()
    client = MagicMock()
    
    # Mock upload to fail twice with connection error, then succeed
    mock_upload = MagicMock()
    mock_upload.side_effect = [
        Exception("WinError 10054 Connection reset"),
        Exception("Connection timeout"),
        "Success!"
    ]
    client.files.upload = mock_upload
    
    # We'll patch time.sleep to avoid waiting during test
    with patch('time.sleep', return_value=None):
        result = processor._upload_file_with_retry(client, "dummy_path", max_retries=3, initial_delay=0.1)
        
    print(f"Result: {result}")
    assert result == "Success!"
    assert mock_upload.call_count == 3
    print("✅ _upload_file_with_retry logic verified with mocked failures.")

def test_critical_failure():
    print("\nTesting critical failure (non-connection error)...")
    processor = VideoProcessor()
    client = MagicMock()
    
    mock_upload = MagicMock()
    mock_upload.side_effect = Exception("403 Permission Denied")
    client.files.upload = mock_upload
    
    try:
        processor._upload_file_with_retry(client, "dummy_path", max_retries=3)
        assert False, "Should have raised Exception"
    except Exception as e:
        print(f"Caught expected critical error: {e}")
        assert "403" in str(e)
        assert mock_upload.call_count == 1
    
    print("✅ Critical failure handling verified (no retry for non-connection errors).")

if __name__ == "__main__":
    try:
        test_retry_logic()
        test_critical_failure()
        print("\nVideoProcessor retry logic checks passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
