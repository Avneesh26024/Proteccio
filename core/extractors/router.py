import os
from core.extractors import pdf_extractor, txt_extractor, csv_extractor

def route(path: str, ocr_provider=None) -> dict:
    """Routes the file to the correct extractor based on extension.

    Args:
        path: Path to the file to extract text from.
        ocr_provider: An optional :class:`core.ocr.base.OCRProvider` instance.
            When provided, it is forwarded to the PDF extractor so that OCR
            is used instead of PyMuPDF. Ignored for .txt and .csv files.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == '.pdf':
        return pdf_extractor.extract(path, ocr_provider=ocr_provider)
    elif ext == '.txt':
        return txt_extractor.extract(path)
    elif ext == '.csv':
        return csv_extractor.extract(path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .pdf, .txt, and .csv are supported.")

if __name__ == "__main__":
    print("Testing Router logic...")
    
    # Create temporary dummy files
    dummy_files = ["test_router.txt", "test_router.csv"]
    with open(dummy_files[0], "w") as f: f.write("test")
    import pandas as pd
    pd.DataFrame({"A": [1]}).to_csv(dummy_files[1], index=False)
    
    for f in dummy_files:
        try:
            print(f"\nRouting {f}...")
            result = route(f)
            print(f"Routed successfully. Metadata: {result['metadata']}")
        except Exception as e:
            print(f"Error on {f}: {e}")
            
    # Test unsupported extension
    try:
        print("\nRouting unsupported.jpg...")
        with open("unsupported.jpg", "w") as f: f.write("fake image")
        route("unsupported.jpg")
    except Exception as e:
        print(f"Correctly caught error: {e}")
        os.remove("unsupported.jpg")

    # Cleanup
    for f in dummy_files:
        if os.path.exists(f):
            os.remove(f)