"""AI-powered document parser using Claude to extract family tree data.

Given a document (image or PDF), uses Claude's vision and text capabilities
to extract structured family information: people, relationships, events, dates.
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Supported file types
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DOC_TYPES = {".pdf"}
ALL_TYPES = IMAGE_TYPES | DOC_TYPES

SYSTEM_PROMPT = """You are a genealogy research assistant. You extract structured family tree data from documents, photos, and records.

Given a document, extract ALL family information you can find and return it as JSON.

IMPORTANT RULES:
1. Match people to existing records when possible (use the provided existing_people list)
2. For new people not in existing records, use id format: "new-firstname-surname" (lowercase, hyphenated)
3. Use ISO date format: YYYY-MM-DD (partial dates OK: YYYY or YYYY-MM)
4. For relationships, parent_id/child_id must reference valid person IDs
5. Be conservative: only extract facts clearly stated or shown in the document
6. Include a confidence note for uncertain information

Return ONLY valid JSON with this exact structure:
{
  "summary": "Brief description of what this document contains",
  "people": [
    {
      "id": "existing-id or new-firstname-surname",
      "is_new": true/false,
      "given_name": "...",
      "surname": "...",
      "gender": "male|female|unknown",
      "birth_date": "YYYY-MM-DD or null",
      "birth_place": "... or null",
      "death_date": "YYYY-MM-DD or null",
      "death_place": "... or null",
      "maiden_name": "... or null",
      "notes": "Any biographical info from the document"
    }
  ],
  "relationships": [
    {
      "parent_id": "...",
      "child_id": "...",
      "rel_type": "biological|adoptive|step|foster"
    }
  ],
  "events": [
    {
      "person_id": "...",
      "event_type": "birth|death|marriage|divorce|immigration|emigration|education|career|military|residence|custom",
      "date": "YYYY-MM-DD or null",
      "end_date": "null or YYYY-MM-DD for spans",
      "place": "... or null",
      "description": "..."
    }
  ],
  "unions": [
    {
      "partner1_id": "...",
      "partner2_id": "...",
      "union_date": "YYYY-MM-DD or null",
      "union_place": "... or null"
    }
  ],
  "notes": "Any additional context, uncertainties, or things that need human verification"
}"""


def _get_client():
    """Get Anthropic client, importing lazily."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    return anthropic.Anthropic(api_key=api_key)


def _extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber package not installed. Run: pip install pdfplumber"
        )

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

    return "\n\n".join(text_parts)


def _encode_image(file_path: str) -> tuple[str, str]:
    """Read and base64-encode an image file. Returns (base64_data, media_type)."""
    ext = Path(file_path).suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(ext, "image/jpeg")

    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")

    return data, media_type


def _build_existing_people_context(existing_people: list[dict]) -> str:
    """Format existing people list for the AI prompt."""
    if not existing_people:
        return "No existing people in the family tree yet."

    lines = ["Existing people in the family tree (use these IDs when matching):"]
    for p in existing_people:
        name = f"{p.get('given_name', '')} {p.get('surname', '')}".strip()
        extras = []
        if p.get("birth_date"):
            extras.append(f"b.{p['birth_date']}")
        if p.get("death_date"):
            extras.append(f"d.{p['death_date']}")
        if p.get("maiden_name"):
            extras.append(f"née {p['maiden_name']}")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"  - id=\"{p['id']}\": {name}{extra_str}")

    return "\n".join(lines)


def parse_document(
    file_path: str,
    existing_people: list[dict],
    document_filename: str = "",
) -> dict[str, Any]:
    """Parse a document and extract family tree data using Claude.

    Args:
        file_path: Absolute path to the uploaded file
        existing_people: List of existing person dicts (from API) for matching
        document_filename: Original filename for context

    Returns:
        Parsed data dict with people, relationships, events, unions, notes
    """
    client = _get_client()
    ext = Path(file_path).suffix.lower()

    people_context = _build_existing_people_context(existing_people)

    user_prompt = f"""Analyze this document and extract all family tree information.

Document filename: {document_filename or Path(file_path).name}

{people_context}

Extract all people, relationships, dates, places, and events. Match people to existing records where possible. Return ONLY valid JSON."""

    # Build message content based on file type
    content: list[dict] = []

    if ext == ".pdf":
        # Extract text from PDF
        pdf_text = _extract_pdf_text(file_path)
        if not pdf_text.strip():
            # If no text extracted, try sending pages as images
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for i, page in enumerate(pdf.pages[:10]):  # max 10 pages
                        img = page.to_image(resolution=200)
                        import io
                        buf = io.BytesIO()
                        img.original.save(buf, format="PNG")
                        b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        })
            except Exception as e:
                logger.warning("Could not render PDF pages as images: %s", e)
                return {"error": f"PDF has no extractable text and could not be rendered: {e}"}
        else:
            user_prompt += f"\n\nDocument text:\n{pdf_text}"
    elif ext in IMAGE_TYPES:
        # Send image directly to Claude vision
        b64_data, media_type = _encode_image(file_path)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_data,
            },
        })

    content.append({"type": "text", "text": user_prompt})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        # Extract JSON from response
        response_text = response.content[0].text

        # Try to parse JSON (handle markdown code blocks)
        json_text = response_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]

        parsed = json.loads(json_text.strip())
        return parsed

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: %s", e)
        return {
            "error": f"AI returned invalid JSON: {e}",
            "raw_response": response_text[:2000] if 'response_text' in dir() else "",
        }
    except Exception as e:
        logger.error("Document parsing failed: %s", e)
        return {"error": str(e)}
