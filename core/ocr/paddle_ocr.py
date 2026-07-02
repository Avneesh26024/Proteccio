from core.ocr.base import OCRProvider


class PaddleOCRProvider(OCRProvider):
    """OCR provider powered by PaddleOCR.
    
    PaddleOCR v3 is imported lazily inside ``extract()`` to avoid slowing
    down application startup and to prevent crashes if the dependency is missing.
    """

    @property
    def name(self) -> str:
        """Return the canonical provider name."""
        return "paddleocr"

    def extract(self, file_path: str) -> str:
        """Extract text from a PDF using PaddleOCR.

        Since PaddleOCR primarily processes images, this method uses ``pdf2image``
        to rasterise the PDF pages first, then runs OCR on each resulting image.

        Args:
            file_path: Path to the PDF file to process.

        Returns:
            Extracted and cleaned text as a single string.

        Raises:
            ImportError: If ``paddleocr`` or ``pdf2image`` are not installed.
            RuntimeError: If PDF rasterisation fails (e.g. missing poppler).
            ValueError: If PaddleOCR returns empty text for the given file.
        """
        # ------------------------------------------------------------------
        # Lazy imports to ensure application safety
        # ------------------------------------------------------------------
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            raise ImportError(
                "PaddleOCR is not installed. Run: pip install paddleocr"
            )

        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image is not installed. Run: pip install pdf2image"
            )

        import numpy as np

        # ------------------------------------------------------------------
        # Rasterise PDF to images (200 DPI is a good balance for OCR)
        # ------------------------------------------------------------------
        try:
            images = convert_from_path(file_path, dpi=200)
        except Exception as e:
            raise RuntimeError(
                f"Failed to convert PDF to images. Ensure 'poppler-utils' is "
                f"installed on your system. Details: {e}"
            )

        if not images:
            raise ValueError(f"No pages found in PDF: {file_path}")

        # ------------------------------------------------------------------
        # Run PaddleOCR v3 on each page image
        # ------------------------------------------------------------------
        # In PaddleOCR v3, the API uses predict() and returns an OCRResult object
        # which behaves like a dictionary containing 'rec_texts'.
        ocr = PaddleOCR(use_textline_orientation=True, lang="en")
        
        extracted_lines = []
        for img in images:
            img_array = np.array(img)
            try:
                result_list = ocr.predict(img_array)
                if result_list and len(result_list) > 0:
                    res_dict = result_list[0]
                    if "rec_texts" in res_dict:
                        for text in res_dict["rec_texts"]:
                            if text and isinstance(text, str):
                                extracted_lines.append(text)
            except Exception as ocr_err:
                print(f"[PaddleOCR Warning] Failed to process a page: {ocr_err}")
                continue

        full_text = "\n".join(extracted_lines).strip()
        
        if not full_text:
            raise ValueError(
                f"PaddleOCR returned empty text for: {file_path}"
            )

        return full_text
