from core.ocr.base import OCRProvider


class DoclingOCR(OCRProvider):
    """OCR provider powered by IBM's Docling library (v2+).

    Docling is imported lazily inside ``extract()`` so that the rest of the
    application starts cleanly even when the library is not installed.

    Configuration used:
    - RapidOCR backend forced to ``onnxruntime`` (avoids the torch/PP-OCRv6
      incompatibility that surfaces with the default auto-detect backend).
    - Language set to ``["en"]`` for English documents.
    - OCR only applied when Docling detects bitmap regions (``do_ocr=True``
      with the default area threshold); text-layer PDFs are handled natively.
    """

    @property
    def name(self) -> str:
        """Return the canonical provider name."""
        return "docling"

    def extract(self, file_path: str) -> str:
        """Extract text from a PDF using Docling's DocumentConverter.

        Args:
            file_path: Path to the PDF file to process.

        Returns:
            Extracted and cleaned text as a single string.

        Raises:
            ImportError: If the ``docling`` package is not installed.
            RuntimeError: If Docling's internal OCR engine fails to initialise
                (e.g. missing model weights or unsupported backend config).
            ValueError: If Docling returns empty text for the given file.
        """
        # ------------------------------------------------------------------
        # Lazy import — keeps startup crash-free when docling is absent
        # ------------------------------------------------------------------
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import (
                PdfPipelineOptions,
                RapidOcrOptions,
            )
            from docling.datamodel.base_models import InputFormat
        except ImportError:
            raise ImportError(
                "Docling is not installed. Run: pip install docling"
            )

        # ------------------------------------------------------------------
        # Configure pipeline: force onnxruntime backend + English language
        # This avoids the "Unsupported configuration: torch.PP-OCRv6.*" error
        # that occurs when the torch backend tries to load PPOCRv6 models.
        # ------------------------------------------------------------------
        try:
            ocr_options = RapidOcrOptions(
                backend="onnxruntime",
                lang=["en"],
                print_verbose=False,
            )

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True
            pipeline_options.ocr_options = ocr_options

            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    )
                }
            )
        except Exception as init_err:
            raise RuntimeError(
                f"Docling OCR engine failed to initialise. "
                f"This may be due to missing model weights or an incompatible "
                f"rapidocr/onnxruntime installation. "
                f"Details: {init_err}\n"
                f"Try: pip install --upgrade docling rapidocr-onnxruntime"
            ) from init_err

        # ------------------------------------------------------------------
        # Convert and extract text
        # ------------------------------------------------------------------
        try:
            result = converter.convert(file_path)
        except Exception as conv_err:
            raise RuntimeError(
                f"Docling conversion failed for '{file_path}'. "
                f"Details: {conv_err}"
            ) from conv_err

        # Prefer document-level markdown export (most reliable across versions)
        full_text = ""
        if hasattr(result.document, "export_to_markdown"):
            full_text = result.document.export_to_markdown().strip()

        # Fallback: iterate pages
        if not full_text:
            pages = result.document.pages if hasattr(result.document, "pages") else []
            text_parts = []
            for page in pages:
                if hasattr(page, "export_to_markdown"):
                    text_parts.append(page.export_to_markdown())
                elif hasattr(page, "text"):
                    text_parts.append(page.text or "")
            full_text = "\n".join(text_parts).strip()

        if not full_text:
            raise ValueError(
                f"Docling OCR returned empty text for: {file_path}"
            )

        return full_text
