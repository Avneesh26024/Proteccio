# Proteccio Compliance — Sensitive Data Detection Assistant

A lightweight, privacy-first document analysis pipeline that detects **deterministic and probabilistic PII**, assesses compliance risk, and provides an interactive QA chatbot — all while guaranteeing that **zero raw PII is ever transmitted to external LLM APIs**.

Built for enterprise compliance scenarios where privacy, auditability, and lightweight deployability (including Streamlit Community Cloud) must coexist.

---

## Table of Contents

1. [Key Features](#key-features)
2. [System Architecture](#system-architecture)
3. [Key Architectural Decisions](#key-architectural-decisions)
4. [Project Structure](#project-structure)
5. [Setup & Installation](#setup--installation)
6. [Running the Application](#running-the-application)
7. [Configuration](#configuration)
8. [Pipeline Walkthrough](#pipeline-walkthrough)
9. [Future Roadmap](#future-roadmap)

---

## Key Features

| Feature | Description |
|---|---|
| **Deterministic PII Detection** | Regex engine detects Aadhaar, PAN, email, phone, credit card, bank details, API keys, and employee IDs — each returned with precise character-offset spans for location-aware downstream processing. |
| **Probabilistic PII Detection** | LLM-powered scanner flags confidential business information (project code names, internal metrics, classification markings) and ambiguous sensitive numbers (PINs, OTPs) that regex cannot reliably catch. Returns a `confidence` score per flag (High / Medium / Low). |
| **"Zero-PII" Option A Masking** | Unique, reversible redaction tokens (`[REDACTED_EMAIL_1]`, `[REDACTED_PAN_1]`, …) are generated **locally**. A `detection_map` maintains the token → original value reverse-lookup. The LLM receives only masked text. |
| **In-Memory Pseudo-RAG** | Documents are chunked with configurable sliding windows. Each chunk is tagged with the PII spans that fall within its character range — enabling location-aware chatbot answers without a vector database. |
| **"User-as-Validator" OCR Routing** | A two-step UI shows a lightweight PyMuPDF text preview first. If the PDF is scanned (garbage output), the user selects a heavy OCR fallback (PaddleOCR or Docling) before triggering the full analysis. |
| **Modular OCR Abstract Layer** | `OCRProvider` ABC with a lazy-import factory ensures heavy OCR dependencies never crash the app at startup if not installed. |
| **Risk Scoring** | Configurable severity weights per entity type. A capped scoring formula (`min(count, 5) × weight`) prevents outlier documents from inflating scores. Produces Low / Medium / High risk levels. |
| **Enterprise Audit Logging** | Every pipeline event (analysis complete, LLM call, chatbot query) is appended as a structured JSON line to `outputs/audit_log.jsonl` with a UTC timestamp. |
| **Interactive Chatbot** | A two-path chatbot: statistical router for count-based questions (no LLM call needed), and a pseudo-RAG LLM path for qualitative questions with the top-3 most relevant chunks injected as context. |
| **Streamlit UI + CLI** | Full-featured Streamlit web app with a Document Diff tab (side-by-side original vs. masked), and a headless CLI with optional `--chat` flag. |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          app.py / cli.py                            │
│                   (Streamlit UI  /  CLI Interface)                  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       core/analyzer.py                              │
│                    (Pipeline Orchestrator)                           │
│                                                                     │
│  1. Extract  ──►  core/extractors/router.py                         │
│                       ├── pdf_extractor.py  (PyMuPDF)               │
│                       ├── txt_extractor.py                          │
│                       └── csv_extractor.py                          │
│                             ▲ OCR fallback via                      │
│                             └── core/ocr/factory.py                 │
│                                  ├── DoclingOCR                     │
│                                  └── PaddleOCRProvider              │
│                                                                     │
│  2. Detect   ──►  core/detectors/regex_detector.py  (spans)        │
│              ──►  core/detectors/llm_detector.py    (flags)        │
│                                                                     │
│  3. Mask     ──►  core/masker.py                                    │
│                       └── Returns (masked_text, detection_map)      │
│                                                                     │
│  4. Chunk    ──►  core/chunker.py                                   │
│                       └── Sliding window + span-to-chunk mapping    │
│                                                                     │
│  5. Score    ──►  core/risk_scorer.py                               │
│                                                                     │
│  6. Audit    ──►  core/audit_logger.py  → outputs/audit_log.jsonl  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ result dict
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   core/report_generator.py                          │
│    Sends ONLY masked_text to LLM → compliance_report (3 sections)   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       core/chatbot.py                               │
│   Statistical router  ──►  direct count lookups (no LLM)           │
│   Qualitative router  ──►  top-3 chunk retrieval + LLM call        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Decisions

These decisions reflect deliberate trade-offs to balance privacy, accuracy, and lightweight deployability.

### 1. Why "Option A" Masking? (Local Token Mapping)

> **Problem:** Sending raw PII (emails, Aadhaar numbers, bank account details) to a third-party LLM API is a direct compliance violation under GDPR, DPDP, and similar frameworks.

**Solution:** Before any LLM call, `core/masker.py` replaces every detected value with a **unique, numbered token** (`[REDACTED_EMAIL_1]`, `[REDACTED_AADHAAR_1]`, etc.) and stores the reverse-lookup in a local `detection_map` dictionary:

```
detection_map = {
    "[REDACTED_EMAIL_1]":  "john@example.com",
    "[REDACTED_PAN_1]":    "ABCDE1234F",
}
```

The LLM (Gemini) only ever sees tokens. The `detection_map` lives exclusively in the server's session state and is never transmitted externally. During Chatbot QA, the tokens in LLM responses can be reverse-looked-up if the user requests the actual value (a future feature). Tokens are generated longest-first to prevent substring clobbering.

**Alternatives considered:** Option B (full text withholding) would cripple the LLM's ability to write a useful compliance report. Option C (on-device LLM) was ruled out for lightweight deployment targets.

---

### 2. Why "Pseudo-RAG" (In-Memory Chunking) instead of a Vector Database?

> **Problem:** Full RAG pipelines require FAISS or ChromaDB, which add hundreds of megabytes of native dependencies, GPU/SIMD requirements, and persistent index management — all of which are incompatible with Streamlit Community Cloud's 1 GB memory limit.

**Solution:** `core/chunker.py` implements a sliding-window chunker (default: 1000 chars, 100-char overlap) that maps PII detections to specific chunks using their **character-offset spans** from `regex_detector`. Each chunk knows exactly which PII entities fall within it:

```python
{
    "chunk_index": 2,
    "text": "...Bank account no: 987654...",
    "contained_detections": {"bank_details": ["987654321098"]}
}
```

At query time, the chatbot extracts keywords from the user's question, scores all chunks by keyword hit-count, and injects the **top-3 matching chunks** into the LLM prompt as `RELEVANT EXCERPTS`. This achieves location-awareness ("The credit card number appears in the second paragraph") with **zero vector overhead** — everything lives in Streamlit's `session_state`.

**Trade-off accepted:** Keyword matching is less semantically precise than cosine-similarity over embeddings. For the document sizes this tool targets (< 50 pages), keyword matching is accurate enough and orders of magnitude cheaper.

---

### 3. Why "User-as-Validator" OCR Routing?

> **Problem:** Heavy OCR models (Docling, PaddleOCR) require 500 MB – 3 GB of model weights and cannot be bundled into a lightweight cloud deployment.

**Solution:** The pipeline defaults to `PyMuPDF` (fast, zero-ML, sub-second) for all PDF text extraction. If a PDF is scanned/image-based, PyMuPDF returns empty or garbage text. The Streamlit UI exposes this immediately by showing a **text preview** after a lightweight extraction pass.

The **user acts as the validator**: if the preview looks correct, they proceed directly to the full analysis. If the preview is garbled, they select an OCR provider (PaddleOCR or Docling) from a dropdown — and only then is the heavy model loaded.

This is implemented via **lazy imports** inside each provider's `extract()` method, so the app never crashes at startup if these libraries are absent:

```python
# core/ocr/docling_ocr.py
def extract(self, file_path):
    try:
        from docling.document_converter import DocumentConverter  # lazy
    except ImportError:
        raise ImportError("Docling is not installed. Run: pip install docling")
```

The `OCRProvider` ABC and `get_ocr_provider()` factory use `importlib.import_module()` to load provider modules on-demand, so even the module itself is not imported until explicitly requested.

---

## Project Structure

```
Proteccio_Compliance/
│
├── app.py                      # Streamlit web application
├── cli.py                      # Headless command-line interface
├── config.yaml                 # Severity weights, thresholds, LLM settings
├── requirements.txt
│
├── core/
│   ├── analyzer.py             # Pipeline orchestrator (8-step flow)
│   ├── masker.py               # Option A token masking + detection_map
│   ├── chunker.py              # Sliding-window chunker / Pseudo-RAG
│   ├── risk_scorer.py          # Weighted risk scoring + Low/Medium/High
│   ├── report_generator.py     # LLM compliance report (masked text only)
│   ├── chatbot.py              # Two-path chatbot (statistical + RAG-LLM)
│   ├── audit_logger.py         # JSONL audit event appender
│   │
│   ├── detectors/
│   │   ├── regex_detector.py   # Deterministic PII (span-dict output)
│   │   └── llm_detector.py     # Probabilistic PII (confidence-scored flags)
│   │
│   ├── extractors/
│   │   ├── router.py           # File-type router (ocr_provider passthrough)
│   │   ├── pdf_extractor.py    # PyMuPDF + optional OCR override
│   │   ├── txt_extractor.py
│   │   └── csv_extractor.py
│   │
│   ├── ocr/
│   │   ├── base.py             # OCRProvider ABC
│   │   ├── docling_ocr.py      # Docling provider (lazy import)
│   │   ├── paddle_ocr.py       # PaddleOCR provider (lazy import)
│   │   └── factory.py          # importlib-based registry + get_ocr_provider()
│   │
│   └── providers/
│       ├── base.py             # LLMProvider ABC
│       ├── gemini.py           # Google Gemini (google-genai SDK)
│       └── factory.py          # get_provider() factory
│
└── outputs/                    # Auto-created; stores reports and audit log
    ├── report.txt
    ├── masked_document.txt
    └── audit_log.jsonl
```

---

## Setup & Installation

### Prerequisites

- Python **3.10 or higher**
- A [Google AI Studio](https://aistudio.google.com/) API key (free tier available)

### 1. Clone the repository

```bash
git clone <repository-url>
cd Proteccio_Compliance
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows
```

### 3. Install core dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

Create a `.env` file in the project root:

```bash
# .env
GEMINI_API_KEY=your_google_ai_studio_key_here
```

> **Note:** The `.env` file is listed in `.gitignore` and will never be committed.

### 5. Optional: Heavy OCR dependencies

The core pipeline works without these. Install them **only if you need OCR on scanned PDFs**:

```bash
# PaddleOCR (+ pdf2image for PDF-to-image rasterisation)
pip install paddleocr pdf2image

# Docling (IBM's document understanding engine — large download)
pip install docling
```

These packages are imported **lazily** — the app will not crash at startup if they are absent. They are only loaded when the user explicitly selects an OCR provider in the UI.

---

## Running the Application

### Streamlit Web UI (recommended)

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`. The two-step flow:
1. Upload a document → click **"1. Preview Extraction"** to verify text quality.
2. Optionally select an OCR fallback → click **"2. Run Full Analysis ✨"**.

### Command-Line Interface

```bash
# Basic analysis + report saved to outputs/
python cli.py --file path/to/document.pdf

# Specify a different LLM provider (future)
python cli.py --file document.pdf --provider gemini

# Run analysis then launch interactive chatbot
python cli.py --file document.pdf --chat

# Run analysis without saving output files
python cli.py --file document.pdf --no-save
```

**Supported file types:** `.pdf`, `.txt`, `.csv`

---

## Configuration

All tunable parameters live in `config.yaml`:

```yaml
severity_weights:       # Points per detected entity (used by risk_scorer.py)
  aadhaar:      10      # Highest severity — biometric-linked national ID
  pan:          10
  credit_card:  10
  bank_details:  9
  api_key:       9
  employee_id:   6
  phone:         5
  email:         3      # Lowest severity

thresholds:             # Score boundaries for risk level labels
  low:    10            # score ≤ 10  → Low
  medium: 30            # score ≤ 30  → Medium
  high:   31            # score > 30  → High

llm_settings:
  model: "gemini-2.5-flash-lite"
  max_chars_for_llm: 50000    # Truncation limit for report generation

pdf_settings:
  max_pages: 50               # PyMuPDF page cap
```

Risk scoring uses a **capped formula**: `score = Σ min(count, 5) × weight`, preventing a document with 100 emails from inflating the score disproportionately.

---

## Pipeline Walkthrough

Given an input document, the 8-step pipeline in `core/analyzer.py` executes as follows:

```
1. EXTRACT   router.route(file, ocr_provider?)
             → {"text": "...", "metadata": {...}}

2. DETECT    regex_detector.detect(text)
             → {"email": [{"value": "x@y.com", "start": 14, "end": 21}], ..., "_counts": {...}}

             llm_detector.detect(text, provider)
             → {"potential_flags": [{"value": "Project Titan", "type": "...", "confidence": "High", ...}]}

3. MASK      masker.mask_text(text, detection_dict)
             → (masked_text, {"[REDACTED_EMAIL_1]": "x@y.com", ...})

4. CHUNK     chunker.chunk_document(text, detection_dict)
             → [{"chunk_index": 0, "text": "...", "contained_detections": {...}}, ...]

5. SCORE     risk_scorer.score(detection_dict)
             → adds "_score": 42, "_risk_level": "High" in-place

6. AUDIT     audit_logger.log_event("analysis_complete", {...})
             → appends one JSON line to outputs/audit_log.jsonl

7. REPORT    report_generator.generate(result, provider)
             → sends ONLY masked_text to Gemini → 3-section compliance report

8. CHATBOT   Chatbot(result, report, provider)
             → stat questions resolved locally; qualitative → top-3 chunks + LLM
```

---

## Future Roadmap

| Area | Planned Enhancement |
|---|---|
| **Multimodal Extraction** | Integration of Vision-Language Models (VLMs) for direct image-PDF analysis, eliminating the need for a separate OCR step entirely. |
| **Persistent Vector RAG** | Replacement of in-memory keyword search with a persistent FAISS / ChromaDB index for deployments on heavier infrastructure (≥ 4 GB RAM), enabling semantic similarity search across very large document corpora. |
| **Compliance Frameworks** | Pluggable ruleset modules for specific standards: GDPR (EU), DPDP (India), HIPAA (healthcare), and SOC 2 — each with framework-specific entity weights and remediation templates. |
| **Multi-Provider LLM Support** | Extending `core/providers/` with OpenAI, Anthropic Claude, and local Ollama providers via the existing `LLMProvider` ABC. |
| **Batch Processing** | CLI and UI support for scanning entire directories of documents and aggregating risk across a corpus. |
| **Token Reversal in Chatbot** | Full round-trip implementation where the chatbot can look up `detection_map` to surface the original PII value when the user explicitly requests it and has appropriate authorization. |

---

## License

This project is submitted as an academic assignment. All rights reserved.
