"""
Medical document extraction using AI inference backends.
Handles PDF text extraction, image extraction, and LLM-based structured summarization.
"""

import io
import json
import logging
import os
from typing import Optional

import pypdfium2 as pdfium

from backend import get_backend, get_vision_backend, get_model, get_num_ctx
from lab_table import parse_lab_tables

logger = logging.getLogger(__name__)

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    with open(os.path.join(_PROMPT_DIR, filename)) as f:
        return f.read().strip()


EXTRACTION_PROMPT = _load_prompt("extraction.md")

_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
    "pt": "Portuguese (Brazilian)",
}


def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, list[bytes]]:
    """Extract text and page images from a PDF using pypdfium2.

    Returns:
        Tuple of (extracted_text, list_of_page_images_as_png_bytes)
    """
    doc = pdfium.PdfDocument(file_bytes)
    text_parts = []
    images = []

    for page in doc:
        textpage = page.get_textpage()
        text_parts.append(textpage.get_text_range())
        textpage.close()

        # Render page as image for vision model fallback
        bitmap = page.render(scale=200 / 72)
        pil_image = bitmap.to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        images.append(buf.getvalue())

    doc.close()
    return "\n".join(text_parts).strip(), images


def _parse_llm_response(response_text: str) -> dict:
    """Parse LLM response, handling markdown code blocks."""
    text = response_text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # OCR sidecars carry page breaks (\f) and other control characters; models
    # echo them inside JSON strings, and strict JSON rejects those.
    return json.loads(text, strict=False)


def _lang_line(language: str) -> str:
    lang_name = _LANGUAGE_NAMES.get(language, "English")
    return f"Respond in {lang_name}. Free-text values (summary, recommendations) must be written in {lang_name}. JSON keys must remain in English.\n\n"


def call_ollama_text(text: str, model: str, language: str = "en") -> dict:
    """Send extracted text to backend for structured extraction. Retries once on bad JSON."""
    prompt = f"{_lang_line(language)}{EXTRACTION_PROMPT}\n\n--- DOCUMENT TEXT ---\n{text}\n--- END ---"
    messages = [{"role": "user", "content": prompt}]
    nctx = get_num_ctx("extract")
    response = get_backend().chat(model, messages, num_ctx=nctx)
    try:
        return _parse_llm_response(response)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Extraction returned invalid JSON, retrying once")
        response = get_backend().chat(model, messages, num_ctx=nctx)
        return _parse_llm_response(response)


def call_ollama_vision(image_bytes: bytes, model: str, language: str = "en") -> dict:
    """Send an image to vision backend for structured extraction. Retries once on bad JSON."""
    prompt = f"{_lang_line(language)}{EXTRACTION_PROMPT}"
    messages = [{"role": "user", "content": prompt}]
    nctx = get_num_ctx("vision")
    response = get_vision_backend().chat(model, messages, images=[image_bytes], num_ctx=nctx)
    try:
        return _parse_llm_response(response)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Vision extraction returned invalid JSON, retrying once")
        response = get_vision_backend().chat(model, messages, images=[image_bytes], num_ctx=nctx)
        return _parse_llm_response(response)


def extract_document(
    file_bytes: bytes,
    content_type: str,
    model: Optional[str] = None,
    language: str = "en",
) -> dict:
    """Main extraction entry point. Routes to text or vision model based on content.

    Returns dict with keys: extracted_text, entities
    """
    model = model or get_model("extract")

    extracted_text = ""
    entities = {}

    if content_type == "application/pdf":
        text, images = extract_text_from_pdf(file_bytes)
        extracted_text = text

        # If substantial text found, use text model; otherwise vision
        if len(text.strip()) > 100:
            logger.info("PDF has substantial text (%d chars), using text model", len(text))
            entities = call_ollama_text(text, model, language)
        elif images:
            logger.info("PDF has little text, using vision model on first page")
            entities = call_ollama_vision(images[0], model, language)
        else:
            return {"extracted_text": "", "entities": {}}
    elif content_type in ("image/png", "image/jpeg", "image/jpg"):
        logger.info("Image file, using vision model")
        entities = call_ollama_vision(file_bytes, model, language)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

    return {
        "extracted_text": extracted_text,
        "entities": entities,
    }


def extract_entities_from_text(
    text: str,
    document_type: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "en",
) -> dict:
    """Extract structured entities from already-OCR'd text.

    Used by the new pipeline (Step 3: extraction stage) where OCR and
    classification have already happened.

    Returns dict with key: entities
    """
    model = model or get_model("extract")

    extra = ""
    if document_type:
        extra = f"\nThis document has been classified as: {document_type}\n"

    # Lab tables are parsed deterministically from the OCR HTML (exact, no LLM
    # guessing, no timeout, ADR 028). Tell the model to skip observations so its
    # output stays small and fast; we inject the parsed rows afterwards.
    lab_obs = parse_lab_tables(text)
    if lab_obs:
        extra += (
            "\nThe lab result tables are already captured separately. Return an empty "
            '"observations" array and focus on summary, diagnoses, medications, and appointments.\n'
        )

    entities = call_ollama_text(extra + text, model, language)
    # The deterministic lab values must not depend on the LLM producing valid JSON —
    # some models return null/invalid here; still surface the parsed observations.
    if not isinstance(entities, dict):
        entities = {}
    if lab_obs:
        entities["observations"] = lab_obs
    # No confidence score: the model gives us none. The 0.85 that used to sit here
    # was invented, and the threshold that read it was never wired up — a fake
    # number is worse than an honest absence (#111).
    return {"entities": entities}
