def mask_text(text: str, detection_dict: dict) -> tuple[str, dict]:
    """Replace detected PII values with unique, reversible redaction tokens.

    Each detected value is replaced with a deterministic token of the form
    ``[REDACTED_<ENTITY_TYPE>_<N>]`` (e.g. ``[REDACTED_EMAIL_1]``).  A
    ``detection_map`` is returned alongside the masked text so that callers
    can reverse-lookup the original value from any token found in the text.

    Sorting values by descending length before replacement guarantees that a
    longer value which contains a shorter one as a substring (e.g. two emails
    where one is a prefix of the other) is replaced first, preventing partial
    matches from corrupting the longer token.

    Args:
        text: The raw document text to mask.
        detection_dict: Output of the PII detector.  Keys are entity type
            strings (e.g. ``"email"``, ``"phone"``) or internal metadata keys
            that start with ``"_"`` (e.g. ``"_counts"``, ``"_risk_level"``).
            Values for entity keys are lists of either:

            * **span dicts** ``{"value": str, "start": int, "end": int}``
              (as produced by the updated ``regex_detector``), or
            * plain strings (legacy / test usage).

            Both formats are handled transparently.

    Returns:
        A tuple ``(masked_text, detection_map)`` where:

        * ``masked_text`` – a copy of ``text`` with every detected PII value
          replaced by its unique redaction token.
        * ``detection_map`` – a dict mapping each token (e.g.
          ``"[REDACTED_EMAIL_1]"``) back to the original raw string.
    """
    masked_text = text
    detection_map: dict[str, str] = {}

    for entity_type, values in detection_dict.items():
        # Skip internal metadata keys (e.g. _counts, _score, _risk_level)
        if entity_type.startswith("_"):
            continue

        # Skip entity types that are not a non-empty list
        if not isinstance(values, list) or not values:
            continue

        # Normalise: accept both span-dicts {value, start, end} and plain strings
        def _to_str(item) -> str:
            return item["value"] if isinstance(item, dict) else str(item)

        # Sort longest-first so substring values don't clobber longer tokens
        sorted_values = sorted(values, key=lambda item: len(_to_str(item)), reverse=True)

        token_prefix = f"[REDACTED_{entity_type.upper()}"

        for idx, item in enumerate(sorted_values, start=1):
            raw_value = _to_str(item)
            token = f"{token_prefix}_{idx}]"

            # Replace every occurrence of the raw value in the working text
            masked_text = masked_text.replace(raw_value, token)

            # Record the reverse-lookup mapping
            detection_map[token] = raw_value

    return masked_text, detection_map


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Smoke test
    # ------------------------------------------------------------------
    sample_text = (
        "User john@example.com has ID EMP-123. "
        "Backup email is jane@example.com. "
        "Aadhaar: [Aadhaar Redacted]."
    )

    sample_detection_dict = {
        "email": ["john@example.com", "jane@example.com"],
        "employee_id": ["EMP-123"],
        "aadhaar": ["[Aadhaar Redacted]"],   # safe mock placeholder
        "_counts": {"email": 2, "employee_id": 1},
    }

    masked, d_map = mask_text(sample_text, sample_detection_dict)

    print("=== Masker Smoke Test ===\n")
    print(f"Original text:\n  {sample_text}\n")
    print(f"Masked text:\n  {masked}\n")
    print("Detection map (token → original value):")
    for token, original in d_map.items():
        print(f"  {token!r:35s} → {original!r}")

    # Assertions
    assert "[REDACTED_EMAIL_1]" in masked, "First email not masked"
    assert "[REDACTED_EMAIL_2]" in masked, "Second email not masked"
    assert "[REDACTED_EMPLOYEE_ID_1]" in masked, "Employee ID not masked"
    assert "[REDACTED_AADHAAR_1]" in masked, "Aadhaar placeholder not masked"
    assert "john@example.com" not in masked, "Raw email still present"
    assert "_counts" not in str(d_map), "_counts metadata leaked into map"
    assert len(d_map) == 4, f"Expected 4 map entries, got {len(d_map)}"

    print("\nAll assertions passed ✓")
