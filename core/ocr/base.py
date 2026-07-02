from abc import ABC, abstractmethod


class OCRProvider(ABC):
    """Abstract base class for all OCR providers.
    
    Each concrete provider must implement the `extract` method and the
    `name` property. Heavy dependencies (docling, paddleocr, etc.) must
    be imported lazily *inside* the `extract` method so that a missing
    library never crashes the app at startup.
    """

    @abstractmethod
    def extract(self, file_path: str) -> str:
        """Extract text from the file at the given path.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            The extracted text as a single string.

        Raises:
            ValueError: If extraction succeeds but returns empty text.
            ImportError: If a required OCR dependency is not installed.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider's canonical name (e.g. 'docling')."""
        ...
