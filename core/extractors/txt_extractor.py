import os

def extract(path: str) -> dict:
    """Extracts and cleans text from a TXT file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    # Graceful encoding fallback
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='latin-1') as f:
            content = f.read()

    # Clean the text
    cleaned_text = content.replace('\x00', '').strip()
    cleaned_text = cleaned_text.replace('\r\n', '\n').replace('\r', '\n')

    return {
        "text": cleaned_text,
        "metadata": {
            "file_name": os.path.basename(path),
            "char_count": len(cleaned_text),
            "line_count": len(cleaned_text.splitlines())
        }
    }

if __name__ == "__main__":
    # Test script - will create a dummy text file to test
    test_file = "test_sample.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("Hello world!\r\nThis is a test document.\x00\nWith some messy formatting.  ")
        
    print(f"Testing TXT Extractor on '{test_file}'...")
    result = extract(test_file)
    print("Success! Metadata:")
    print(result["metadata"])
    print("\nCleaned Text:")
    print(repr(result["text"])) # Using repr to show exact whitespace/newlines
    
    # Cleanup
    os.remove(test_file)