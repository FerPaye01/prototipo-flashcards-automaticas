import os

def test_recovery_parse():
    # Sample content as saved by video_processor
    content = """# Segmento 1
# Tiempo: 0:00-12:00
# Duración: 720.0s
# Caracteres: 100

This is the actual transcription text.
It has multiple lines.
"""
    # Create temp file
    with open("test_trans.txt", "w", encoding="utf-8") as f:
        f.write(content)
        
    # Test logic (mimic anki_import_interface.py fix)
    try:
        with open("test_trans.txt", "r", encoding="utf-8") as f:
            read_content = f.read()
            # The FIX: split on '\n' instead of '\\n'
            lines = [line for line in read_content.split('\n') if not line.startswith('#')]
            text = '\n'.join(lines).strip()
            char_count = len(text)
            
        print(f"Parsed text: '{text}'")
        print(f"Char count: {char_count}")
        
        # Original BUG test (for comparison):
        buggy_lines = [line for line in read_content.split('\\n') if not line.startswith('#')]
        buggy_text = '\\n'.join(buggy_lines).strip()
        print(f"Buggy text was empty? {buggy_text == ''}")
        
        assert char_count > 0
        assert "actual transcription" in text
        print("✅ Recovery parsing logic verified.")
        
    finally:
        if os.path.exists("test_trans.txt"):
            os.remove("test_trans.txt")

if __name__ == "__main__":
    test_recovery_parse()
