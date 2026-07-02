import json
import os
from datetime import datetime


def log_event(
    event_type: str,
    data: dict,
    log_file: str = "outputs/audit_log.jsonl",
) -> None:
    """Append a structured audit event to a JSONL file.

    Each call writes exactly one JSON line to ``log_file``.  The file is
    created on first use; the ``outputs/`` directory is created automatically
    if it does not exist.

    Args:
        event_type: A short, human-readable label for the event
            (e.g. ``"document_scanned"``, ``"report_generated"``).
        data: Arbitrary metadata to store alongside the event.  Must be
            JSON-serialisable.
        log_file: Path to the append-only JSONL log file.  Defaults to
            ``outputs/audit_log.jsonl`` relative to the working directory.
    """
    # Ensure the parent directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    payload = {
        "timestamp":  datetime.utcnow().isoformat(),
        "event_type": event_type,
        "data":       data,
    }

    with open(log_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    import tempfile

    print("=== Audit Logger Smoke Test ===\n")

    # Use a temp file so the test never pollutes the real log
    with tempfile.NamedTemporaryFile(
        mode="r", suffix=".jsonl", delete=False
    ) as tmp:
        tmp_path = tmp.name

    # Write three events
    log_event("document_scanned",   {"file": "sample.pdf", "pages": 3},     log_file=tmp_path)
    log_event("pii_detected",       {"email": 2, "phone": 1},               log_file=tmp_path)
    log_event("report_generated",   {"report_id": "RPT-001", "risk": "High"}, log_file=tmp_path)

    # Read back and verify
    with open(tmp_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    print(f"Lines written: {len(lines)}")
    for line in lines:
        parsed = json.loads(line)
        print(f"  [{parsed['timestamp']}] {parsed['event_type']} → {parsed['data']}")

    # Assertions
    assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}"

    events = [json.loads(ln) for ln in lines]
    assert events[0]["event_type"] == "document_scanned"
    assert events[1]["event_type"] == "pii_detected"
    assert events[2]["event_type"] == "report_generated"
    assert events[2]["data"]["risk"] == "High"

    for ev in events:
        assert "timestamp"  in ev, "Missing timestamp"
        assert "event_type" in ev, "Missing event_type"
        assert "data"       in ev, "Missing data"
        # timestamp must be a valid ISO 8601 string
        datetime.fromisoformat(ev["timestamp"])

    # Cleanup
    os.remove(tmp_path)

    print("\nAll assertions passed ✓")
