def chunk_document(
    text: str,
    detections: dict,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[dict]:
    """Slide a window across ``text`` and map span-based detections to chunks.

    Each chunk records which PII values physically fall within its character
    range, building a per-chunk detection index for the pseudo-RAG pipeline.

    Args:
        text: The full document text to chunk.
        detections: Output of :func:`core.detectors.regex_detector.detect`.
            Entity keys map to lists of ``{"value", "start", "end"}`` dicts.
            Metadata keys (starting with ``"_"``) are ignored.
        chunk_size: Number of characters per chunk window.
        overlap: Number of characters the next chunk re-reads from the
            previous one.  Must be less than ``chunk_size``.

    Returns:
        A list of chunk dicts, each shaped::

            {
                "chunk_index":          int,
                "text":                 str,
                "contained_detections": {"entity_type": ["unique_value", ...]}
            }
    """
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})."
        )

    chunks: list[dict] = []
    step = chunk_size - overlap
    doc_len = len(text)
    chunk_index = 0
    pos = 0

    while pos < doc_len:
        start_char = pos
        end_char   = min(pos + chunk_size, doc_len)

        chunk_text = text[start_char:end_char]

        # ------------------------------------------------------------------
        # Map detections whose span overlaps this chunk's character range
        # ------------------------------------------------------------------
        contained: dict[str, list[str]] = {}

        for entity_type, spans in detections.items():
            # Skip internal metadata keys
            if entity_type.startswith("_"):
                continue
            if not isinstance(spans, list):
                continue

            unique_values: list[str] = []
            seen: set[str] = set()

            for span in spans:
                # A detection "belongs" to a chunk when its span start or end
                # falls within the chunk's character window.
                d_start = span.get("start", 0)
                d_end   = span.get("end",   0)
                if d_start < end_char and d_end > start_char:
                    val = span.get("value", "")
                    if val and val not in seen:
                        unique_values.append(val)
                        seen.add(val)

            if unique_values:
                contained[entity_type] = unique_values

        chunks.append({
            "chunk_index":          chunk_index,
            "text":                 chunk_text,
            "contained_detections": contained,
        })

        chunk_index += 1
        pos += step

    return chunks


if __name__ == "__main__":
    print("=== Chunker Smoke Test ===\n")

    # Short enough text that we can reason about positions precisely
    sample_text = (
        "User john@example.com called support. "          # 0–38
        "They reported card 4111-1111-1111-1111. "        # 39–79
        "Contact jane@example.com for follow-up."         # 80–119
    )

    # Minimal detection dict mimicking regex_detector output
    sample_detections = {
        "email": [
            {"value": "john@example.com", "start": 5,  "end": 21},
            {"value": "jane@example.com", "start": 90, "end": 106},
        ],
        "credit_card": [
            {"value": "4111-1111-1111-1111", "start": 59, "end": 78},
        ],
        "_counts": {"email": 2, "credit_card": 1},
    }

    chunks = chunk_document(
        sample_text,
        sample_detections,
        chunk_size=80,
        overlap=10,
    )

    for c in chunks:
        print(f"Chunk {c['chunk_index']} [{c['chunk_index']*70}–{c['chunk_index']*70+80}]")
        print(f"  text preview : {c['text'][:60]!r}...")
        print(f"  detections   : {c['contained_detections']}")
        print()

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------
    # Chunk 0 should contain john@example.com and the credit card
    assert "email"       in chunks[0]["contained_detections"], "chunk 0 missing email"
    assert "john@example.com" in chunks[0]["contained_detections"]["email"]

    # jane@example.com is near the end, should appear in a later chunk
    jane_found = any(
        "jane@example.com" in c["contained_detections"].get("email", [])
        for c in chunks
    )
    assert jane_found, "jane@example.com not found in any chunk"

    # _counts must not leak into contained_detections
    for c in chunks:
        assert "_counts" not in c["contained_detections"], \
            "_counts leaked into contained_detections"

    print("All assertions passed ✓")
