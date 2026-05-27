"""AI-powered document parser using Claude to extract family tree data.

Given a document (image or PDF), uses Claude's vision and text capabilities
to extract structured family information: people, relationships, events, dates.
"""

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

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
        response_text = ""
        stop_reason = None

        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=65536,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        ) as stream:
            for text in stream.text_stream:
                response_text += text
            final = stream.get_final_message()
            stop_reason = final.stop_reason

        # Check if response was truncated
        if stop_reason == "max_tokens":
            logger.warning("Claude response truncated (hit max_tokens)")

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
        truncated = stop_reason == "max_tokens"
        msg = ("AI response was truncated — the document produced too much data. "
               "Try cropping to the most relevant section.") if truncated else f"AI returned invalid JSON: {e}"
        return {
            "error": msg,
            "raw_response": response_text[:2000],
        }
    except Exception as e:
        logger.error("Document parsing failed: %s", e)
        return {"error": str(e)}


# ── Chunked PDF Processing ──────────────────────────────────────────────

TEXT_CHAR_THRESHOLD = 50
MAX_TEXT_PAGES = 10
MAX_IMAGE_PAGES = 5
MAX_TEXT_CHARS = 80_000


def _plan_chunks(file_path: str) -> list[dict]:
    """Classify every PDF page and group consecutive same-mode pages into chunks.

    Returns list of {start_page, end_page, mode, char_count} dicts.
    Page numbers are 1-indexed.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber package not installed. Run: pip install pdfplumber")

    page_info: list[dict] = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            char_count = len(text.strip())
            mode = "text" if char_count >= TEXT_CHAR_THRESHOLD else "image"
            page_info.append({"page": i + 1, "mode": mode, "chars": char_count})

    if not page_info:
        return []

    chunks: list[dict] = []
    current_mode = page_info[0]["mode"]
    current_start = page_info[0]["page"]
    current_chars = page_info[0]["chars"]
    max_pages = MAX_TEXT_PAGES if current_mode == "text" else MAX_IMAGE_PAGES

    for info in page_info[1:]:
        page_count = info["page"] - current_start
        mode_changed = info["mode"] != current_mode
        at_page_limit = page_count >= max_pages
        at_char_limit = current_mode == "text" and (current_chars + info["chars"]) > MAX_TEXT_CHARS

        if mode_changed or at_page_limit or at_char_limit:
            chunks.append({
                "start_page": current_start,
                "end_page": info["page"] - 1,
                "mode": current_mode,
                "char_count": current_chars,
            })
            current_mode = info["mode"]
            current_start = info["page"]
            current_chars = info["chars"]
            max_pages = MAX_TEXT_PAGES if current_mode == "text" else MAX_IMAGE_PAGES
        else:
            current_chars += info["chars"]

    chunks.append({
        "start_page": current_start,
        "end_page": page_info[-1]["page"],
        "mode": current_mode,
        "char_count": current_chars,
    })

    return chunks


def _extract_pdf_text_range(file_path: str, start: int, end: int) -> str:
    """Extract text from a specific page range (1-indexed, inclusive)."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for i in range(start - 1, min(end, len(pdf.pages))):
            page_text = pdf.pages[i].extract_text() or ""
            if page_text.strip():
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

    return "\n\n".join(text_parts)


def _render_pages_as_images(file_path: str, start: int, end: int) -> list[dict]:
    """Render a page range to base64 PNG content blocks for Claude vision."""
    import pdfplumber

    content_blocks = []
    with pdfplumber.open(file_path) as pdf:
        for i in range(start - 1, min(end, len(pdf.pages))):
            img = pdf.pages[i].to_image(resolution=200)
            buf = io.BytesIO()
            img.original.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            })

    return content_blocks


def _call_claude(client, system: str, content: list[dict]) -> dict:
    """Stream a Claude API call and parse the JSON response.

    Extracted from parse_document() for reuse in chunk processing.
    """
    response_text = ""
    stop_reason = None

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=65536,
        system=system,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for text in stream.text_stream:
            response_text += text
        final = stream.get_final_message()
        stop_reason = final.stop_reason

    if stop_reason == "max_tokens":
        logger.warning("Claude response truncated (hit max_tokens)")

    json_text = response_text
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0]
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0]

    try:
        return json.loads(json_text.strip())
    except json.JSONDecodeError as e:
        truncated = stop_reason == "max_tokens"
        msg = ("AI response was truncated — too much data for this chunk. "
               "Results may be incomplete.") if truncated else f"AI returned invalid JSON: {e}"
        return {"error": msg, "raw_response": response_text[:2000]}


def _parse_chunk(
    client,
    file_path: str,
    chunk: dict,
    existing_people: list[dict],
    prior_people: list[dict],
    filename: str,
) -> dict:
    """Process one chunk of a PDF. Returns parsed result dict."""
    start = chunk["start_page"]
    end = chunk["end_page"]
    mode = chunk["mode"]

    people_context = _build_existing_people_context(existing_people)

    prior_context = ""
    if prior_people:
        lines = ["People found in earlier pages of this document (reuse these IDs if you see the same person):"]
        for p in prior_people:
            name = f"{p.get('given_name', '')} {p.get('surname', '')}".strip()
            lines.append(f'  - id="{p["id"]}": {name}')
        prior_context = "\n" + "\n".join(lines) + "\n"

    page_label = f"pages {start}-{end}" if start != end else f"page {start}"
    user_prompt = f"""Analyze {page_label} of this document and extract all family tree information.

Document filename: {filename}

{people_context}
{prior_context}
Extract all people, relationships, dates, places, and events from these pages. Match people to existing records or people from earlier pages where possible. Return ONLY valid JSON."""

    content: list[dict] = []

    if mode == "image":
        content.extend(_render_pages_as_images(file_path, start, end))
    else:
        pdf_text = _extract_pdf_text_range(file_path, start, end)
        if not pdf_text.strip():
            content.extend(_render_pages_as_images(file_path, start, end))
        else:
            user_prompt += f"\n\nDocument text ({page_label}):\n{pdf_text}"

    content.append({"type": "text", "text": user_prompt})

    result = _call_claude(client, SYSTEM_PROMPT, content)

    if "error" not in result:
        result["_page_range"] = [start, end]

    return result


def _merge_chunk_results(chunk_results: list[dict]) -> dict:
    """Merge and deduplicate results from multiple chunks."""
    merged: dict[str, Any] = {
        "summary": "",
        "people": [],
        "relationships": [],
        "events": [],
        "unions": [],
        "notes": "",
    }

    summaries = []
    notes_parts = []
    seen_people: dict[str, dict] = {}
    seen_rels: set[tuple] = set()
    seen_events: set[tuple] = set()
    seen_unions: set[frozenset] = set()

    for result in chunk_results:
        if "error" in result:
            page_range = result.get("_page_range")
            label = f"pages {page_range[0]}-{page_range[1]}" if page_range else "unknown pages"
            notes_parts.append(f"[{label}] Error: {result['error']}")
            continue

        page_range = result.get("_page_range", [0, 0])
        page_label = f"pp.{page_range[0]}-{page_range[1]}" if page_range[0] != page_range[1] else f"p.{page_range[0]}"

        if result.get("summary"):
            summaries.append(f"[{page_label}] {result['summary']}")

        for person in result.get("people", []):
            pid = person.get("id", "")
            if not pid:
                continue
            if pid in seen_people:
                existing = seen_people[pid]
                for field in ("given_name", "surname", "gender", "birth_date", "birth_place",
                              "death_date", "death_place", "maiden_name"):
                    new_val = person.get(field)
                    if new_val and not existing.get(field):
                        existing[field] = new_val
                if person.get("notes"):
                    old_notes = existing.get("notes", "")
                    new_note = f"[{page_label}] {person['notes']}"
                    existing["notes"] = f"{old_notes}; {new_note}" if old_notes else new_note
                existing.setdefault("_source_pages", [])
                existing["_source_pages"].extend(range(page_range[0], page_range[1] + 1))
            else:
                person["_source_pages"] = list(range(page_range[0], page_range[1] + 1))
                seen_people[pid] = person

        for rel in result.get("relationships", []):
            key = (rel.get("parent_id", ""), rel.get("child_id", ""))
            if key[0] and key[1] and key not in seen_rels:
                seen_rels.add(key)
                merged["relationships"].append(rel)

        for event in result.get("events", []):
            key = (event.get("person_id", ""), event.get("event_type", ""), event.get("date", ""))
            if key[0] and key not in seen_events:
                seen_events.add(key)
                merged["events"].append(event)

        for union in result.get("unions", []):
            p1 = union.get("partner1_id", "")
            p2 = union.get("partner2_id", "")
            if p1 and p2:
                key = frozenset([p1, p2])
                if key not in seen_unions:
                    seen_unions.add(key)
                    merged["unions"].append(union)

        if result.get("notes"):
            notes_parts.append(f"[{page_label}] {result['notes']}")

    merged["people"] = list(seen_people.values())
    merged["summary"] = " ".join(summaries)
    merged["notes"] = " ".join(notes_parts)

    return merged


def parse_document_chunked(
    file_path: str,
    existing_people: list[dict],
    filename: str = "",
    on_progress: Optional[Callable] = None,
) -> dict[str, Any]:
    """Main entry point for chunked document parsing.

    For non-PDFs or single-chunk PDFs, delegates to parse_document().
    For multi-chunk PDFs: plans chunks, processes sequentially, merges results.

    Args:
        file_path: Absolute path to the uploaded file
        existing_people: List of existing person dicts for matching
        filename: Original filename for context
        on_progress: Callback(chunk_idx, total, chunk_result) after each chunk
    """
    ext = Path(file_path).suffix.lower()

    if ext != ".pdf":
        return parse_document(file_path, existing_people, filename)

    chunks = _plan_chunks(file_path)

    if len(chunks) <= 1:
        return parse_document(file_path, existing_people, filename)

    logger.info("Splitting PDF into %d chunks for processing", len(chunks))

    client = _get_client()
    chunk_results: list[dict] = []
    prior_people: list[dict] = []

    for idx, chunk in enumerate(chunks):
        logger.info("Processing chunk %d/%d (pages %d-%d, mode=%s)",
                     idx + 1, len(chunks), chunk["start_page"], chunk["end_page"], chunk["mode"])

        result = _parse_chunk(client, file_path, chunk, existing_people, prior_people, filename or Path(file_path).name)
        chunk_results.append(result)

        if "error" not in result:
            for person in result.get("people", []):
                pid = person.get("id", "")
                if pid and not any(p["id"] == pid for p in prior_people):
                    prior_people.append({
                        "id": pid,
                        "given_name": person.get("given_name", ""),
                        "surname": person.get("surname", ""),
                    })

        if on_progress:
            on_progress(idx, len(chunks), result)

    return _merge_chunk_results(chunk_results)
