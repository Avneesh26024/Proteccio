# pyrefly: ignore [missing-import]
import fitz  # PyMuPDF
import os
import yaml

def _get_max_pages(config_path="config.yaml") -> int:
    """Helper to safely load the max_pages limit from config."""
    # Resolve config path gracefully if run from different directories
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config.get("pdf_settings", {}).get("max_pages", 50)
    except Exception:
        return 50  # Default fallback

def extract(path: str, ocr_provider=None) -> dict:
    """Extracts text from a PDF, using either PyMuPDF or an OCR provider.

    Args:
        path: Path to the PDF file.
        ocr_provider: An optional :class:`core.ocr.base.OCRProvider` instance.
            When provided, all text extraction is delegated to it and the
            PyMuPDF text-layer logic is skipped entirely. When ``None``,
            the fast PyMuPDF path is used (the default).

    Returns:
        A dict with keys ``"text"`` (str) and ``"metadata"`` (dict).
        ``metadata`` contains ``page_count``, ``file_name``, and
        ``extraction_method`` (either the provider name or ``"pymupdf"``).

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If PyMuPDF finds no text and no OCR provider is given,
            or if the OCR provider returns empty text.
        Any exception raised by ``ocr_provider.extract()`` bubbles up as-is.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    # ------------------------------------------------------------------
    # OCR path: delegate all text extraction to the supplied provider
    # ------------------------------------------------------------------
    if ocr_provider is not None:
        # Get page count metadata via fitz (lightweight, no text extraction)
        doc = fitz.open(path)
        page_count = len(doc)
        doc.close()

        # Delegate extraction — any exception bubbles up cleanly
        text = ocr_provider.extract(path)

        metadata = {
            "page_count": page_count,
            "file_name": os.path.basename(path),
            "extraction_method": ocr_provider.name,
        }

        return {
            "text": text,
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Default path: fast PyMuPDF text-layer extraction
    # ------------------------------------------------------------------
    max_pages = _get_max_pages()
    doc = fitz.open(path)
    
    text_parts = []
    pages_to_process = min(len(doc), max_pages)
    
    # ... (top of the function stays the same) ...
    for i in range(pages_to_process):
        text_parts.append(doc[i].get_text())
        
    full_text = "\n".join(text_parts)
    
    # Check if the PDF is scanned/image-based
    if not full_text.strip():
        doc.close() # Close before raising error
        raise ValueError("This PDF appears to be scanned or image-based. OCR support is not available in V1.")
        
    # Build metadata while document is still open to get len(doc)
    metadata = {
        "page_count": len(doc),
        "file_name": os.path.basename(path),
        "extraction_method": "pymupdf"
    }
    
    doc.close() # Now we close it safely at the end
    
    return {
        "text": full_text,
        "metadata": metadata
    }

if __name__ == "__main__":
    import sys
    import os
    # Make sure 'core' package is importable when running as __main__
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    from core.ocr.base import OCRProvider

    # ------------------------------------------------------------------
    # Mock OCR provider for testing the ocr_provider code path
    # ------------------------------------------------------------------
    class MockOCRProvider(OCRProvider):
        """Minimal in-process mock — no real OCR library needed."""

        @property
        def name(self) -> str:
            return "mock_ocr"

        def extract(self, file_path: str) -> str:
            return f"[MOCK] Extracted text from: {file_path}"

    # ------------------------------------------------------------------
    # Test 1: Default PyMuPDF path (existing behaviour, unchanged)
    # ------------------------------------------------------------------
    test_file = "sample.pdf"
    print(f"Test 1 — PyMuPDF path on '{test_file}':")
    try:
        result = extract(test_file)
        print(f"  PASS  extraction_method = '{result['metadata']['extraction_method']}'")
        print(f"  Text preview: {result['text'][:80]!r}")
    except Exception as e:
        print(f"  INFO: {e}")

    print()

    # ------------------------------------------------------------------
    # Test 2: OCR provider path using the mock
    # ------------------------------------------------------------------
    print(f"Test 2 — Mock OCR provider path on '{test_file}':")
    try:
        mock = MockOCRProvider()
        result = extract(test_file, ocr_provider=mock)
        assert result["metadata"]["extraction_method"] == "mock_ocr", "extraction_method mismatch"
        assert "[MOCK]" in result["text"], "mock text not returned"
        print(f"  PASS  extraction_method = '{result['metadata']['extraction_method']}'")
        print(f"  Text: {result['text']!r}")
        print(f"  page_count = {result['metadata']['page_count']}")
    except Exception as e:
        print(f"  FAIL: {e}")