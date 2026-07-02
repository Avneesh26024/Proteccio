import importlib

from core.ocr.base import OCRProvider

# ---------------------------------------------------------------------------
# Provider registry
# Maps canonical provider names to their fully-qualified class paths.
# Using strings (not direct imports) keeps heavy modules un-imported until
# the caller explicitly requests a specific provider.
# ---------------------------------------------------------------------------
REGISTRY: dict[str, str] = {
    "docling": "core.ocr.docling_ocr.DoclingOCR",
    "paddleocr": "core.ocr.paddle_ocr.PaddleOCRProvider",
}


def get_ocr_provider(name: str) -> OCRProvider:
    """Dynamically load and return an instantiated OCR provider.

    Only the module containing the requested provider is imported, so heavy
    OCR libraries are never loaded until they are explicitly needed.

    Args:
        name: Case-insensitive provider name (e.g. "docling", "paddleocr").

    Returns:
        An instantiated :class:`OCRProvider` subclass.

    Raises:
        NotImplementedError: If ``name`` is not found in the registry.
    """
    key = name.lower()

    if key not in REGISTRY:
        available = ", ".join(f'"{k}"' for k in REGISTRY)
        raise NotImplementedError(
            f"OCR provider '{name}' is not registered. "
            f"Available providers: {available}"
        )

    # Split "package.module.ClassName" into ("package.module", "ClassName")
    dotted_path = REGISTRY[key]
    module_path, class_name = dotted_path.rsplit(".", maxsplit=1)

    # Dynamically import the module — heavy deps only load here
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    return cls()


# ---------------------------------------------------------------------------
# Quick smoke-tests (run with: python -m core.ocr.factory)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== OCR Factory Smoke Tests ===\n")

    # 1. Test that an invalid name raises NotImplementedError
    print("Test 1: Invalid provider name")
    try:
        get_ocr_provider("invalid_provider")
        print("  FAIL — expected NotImplementedError was not raised")
    except NotImplementedError as exc:
        print(f"  PASS — NotImplementedError raised: {exc}")

    print()

    # 2. Instantiate DoclingOCR and check its name (no .extract() call)
    print("Test 2: Instantiate DoclingOCR")
    try:
        provider = get_ocr_provider("docling")
        print(f"  PASS — provider.name = '{provider.name}'")
    except ImportError as exc:
        # Expected in lightweight environments where docling is not installed
        print(f"  INFO — docling not installed (expected in CI/cloud): {exc}")
    except Exception as exc:
        print(f"  FAIL — unexpected error: {exc}")

    print()

    # 3. Instantiate PaddleOCRProvider and check its name (no .extract() call)
    print("Test 3: Instantiate PaddleOCRProvider")
    try:
        provider = get_ocr_provider("paddleocr")
        print(f"  PASS — provider.name = '{provider.name}'")
    except ImportError as exc:
        # Expected in lightweight environments where paddleocr is not installed
        print(f"  INFO — paddleocr not installed (expected in CI/cloud): {exc}")
    except Exception as exc:
        print(f"  FAIL — unexpected error: {exc}")

    print("\n=== Done ===")
