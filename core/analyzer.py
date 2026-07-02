import os
from core.extractors import router
from core.detectors import regex_detector, llm_detector
from core.risk_scorer import score
from core import masker, chunker, audit_logger


def analyze(file_path: str, ocr_provider=None) -> dict:
    """Orchestrate the full pipeline: Extract → Detect → Mask → Chunk → Score → Audit.

    Args:
        file_path: Path to the document to analyse.
        ocr_provider: Optional :class:`core.ocr.base.OCRProvider` instance.
            When supplied, OCR is used for PDF text extraction instead of
            PyMuPDF.  Defaults to ``None`` (PyMuPDF fast path).

    Returns:
        A comprehensive dict containing:
        ``file_path``, ``metadata``, ``text`` (raw), ``masked_text``,
        ``detection_map``, ``chunks``, and ``detections`` (scored).
    """
    try:
        # ------------------------------------------------------------------
        # Step 1: Extract
        # ------------------------------------------------------------------
        extraction_result = router.route(file_path, ocr_provider=ocr_provider)
        raw_text = extraction_result.get("text", "")
        metadata = extraction_result.get("metadata", {})

        # ------------------------------------------------------------------
        # Step 2: Deterministic detection (regex)
        # ------------------------------------------------------------------
        detection_dict = regex_detector.detect(raw_text)

        # ------------------------------------------------------------------
        # Step 3: Probabilistic detection (LLM stub) — merge flags
        # ------------------------------------------------------------------
        llm_result = llm_detector.detect(raw_text, None)
        detection_dict["potential_flags"] = llm_result.get("potential_flags", [])

        # ------------------------------------------------------------------
        # Step 4: Mask — returns (masked_text, detection_map)
        # ------------------------------------------------------------------
        masked_text, detection_map = masker.mask_text(raw_text, detection_dict)

        # ------------------------------------------------------------------
        # Step 5: Chunk — uses raw text + span-bearing detection_dict
        # ------------------------------------------------------------------
        chunks = chunker.chunk_document(raw_text, detection_dict)

        # ------------------------------------------------------------------
        # Step 6: Score risk (mutates detection_dict in-place)
        # ------------------------------------------------------------------
        scored_detections = score(detection_dict)

        # ------------------------------------------------------------------
        # Step 7: Audit log
        # ------------------------------------------------------------------
        audit_logger.log_event(
            "analysis_complete",
            {
                "file": file_path,
                "risk_level": scored_detections.get("_risk_level"),
                "score": scored_detections.get("_score"),
            },
        )

        # ------------------------------------------------------------------
        # Step 8: Return full pipeline result
        # ------------------------------------------------------------------
        return {
            "file_path":     file_path,
            "metadata":      metadata,
            "text":          raw_text,
            "masked_text":   masked_text,
            "detection_map": detection_map,
            "chunks":        chunks,
            "detections":    scored_detections,
        }

    except ValueError as ve:
        # Re-raise user-facing formatting/extraction errors as-is
        raise ve
    except Exception as e:
        # Wrap system/unexpected errors with context
        raise Exception(f"Analysis failed: {str(e)}")


if __name__ == "__main__":
    import pandas as pd
    import fitz  # PyMuPDF for creating a dummy PDF

    print("Testing Analyzer (full pipeline)...\n")

    # --- Setup dummy test files ---
    test_files = {
        "txt": "test_pipeline.txt",
        "csv": "test_pipeline.csv",
        "pdf": "test_pipeline.pdf",
    }

    # 1. TXT — high risk
    with open(test_files["txt"], "w") as f:
        f.write(
            "Employee ID: EMP-123. Email: test@example.com. "
            "Credit Card: 4111 2222 3333 4444. PAN: ABCDE1234F."
        )

    # 2. CSV — low risk
    pd.DataFrame({
        "Name":  ["Alice", "Bob"],
        "Email": ["alice@example.com", "bob@example.com"],
    }).to_csv(test_files["csv"], index=False)

    # 3. PDF — medium risk
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        "Bank account no: 987654321098, IFSC: SBIN0004321. Phone: 9876543210.",
    )
    doc.save(test_files["pdf"])
    doc.close()

    # --- Run pipeline tests ---
    for f_type, path in test_files.items():
        print(f"=== Testing {f_type.upper()} Pipeline ===")
        try:
            result = analyze(path)

            print(f"  File Path    : {result['file_path']}")
            print(f"  Metadata     : {result['metadata']}")
            print(f"  Risk Level   : {result['detections']['_risk_level']}")
            print(f"  Score        : {result['detections']['_score']}")
            print(f"  Counts       : {result['detections']['_counts']}")
            print(f"  Chunks       : {len(result['chunks'])} chunk(s)")
            print(f"  Detection map: {list(result['detection_map'].keys())}")
            print(f"  Text snippet : {result['text'][:100]!r}\n")

        except Exception as e:
            print(f"  Pipeline failed on {f_type.upper()}: {e}\n")

    # --- Cleanup ---
    for path in test_files.values():
        if os.path.exists(path):
            os.remove(path)

    print("Status: Orchestrator tests completed!")