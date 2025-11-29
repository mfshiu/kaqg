"""Utility to extract text, image descriptions, and table descriptions from a PDF."""
from __future__ import annotations

import argparse
import base64
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import fitz  # PyMuPDF
from langdetect import DetectorFactory, LangDetectException, detect
from openai import OpenAI

# Make language detection deterministic across runs.
DetectorFactory.seed = 0


def _chat_completion_with_handling(client: OpenAI, **kwargs):
    """Call the chat completion API with a friendlier authentication error.

    This wraps the OpenAI client call so that common authentication issues
    produce a clearer message (instead of a long stack trace) while
    preserving the original exception for debugging.
    """

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 - bubble original details
        raise RuntimeError(
            "OpenAI request failed. Ensure OPENAI_API_KEY (or api_key) is set "
            "and valid for the requested model."
        ) from exc


@dataclass
class ExtractionResult:
    """Container for the final list output."""

    items: List[str]


@dataclass
class _ImageTask:
    page_index: int
    order: int
    image_bytes: bytes
    language: str


@dataclass
class _TableTask:
    page_index: int
    order: int
    markdown: str
    language: str


def _determine_language(text: str) -> str:
    """Best-effort language detection returning a human-friendly name."""

    cleaned = text.strip()
    if not cleaned:
        return "English"

    try:
        code = detect(cleaned)
    except LangDetectException:
        return "English"

    code_lower = code.lower()
    code_map = {
        "zh-cn": "zh-cn",
        "zh-tw": "zh-tw",
        "zh": "Chinese",
        "en": "English",
    }
    # code_map = {
    #     "zh-cn": "zh-cn",
    #     "zh-tw": "zh-tw",
    #     "zh": "Chinese",
    #     "ja": "Japanese",
    #     "ko": "Korean",
    #     "es": "Spanish",
    #     "fr": "French",
    #     "de": "German",
    #     "it": "Italian",
    #     "pt": "Portuguese",
    #     "ru": "Russian",
    #     "en": "English",
    # }

    return code_map.get(code_lower, "zh-tw")


def _ensure_pdf_path(path: str | Path) -> Path:
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Input must be a PDF file")
    return pdf_path


def _best_effort_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8 to avoid Windows code page crashes."""

    # If stdout is already UTF-8 (common on macOS/Linux and PowerShell Core),
    # there is nothing to do.
    encoding = getattr(sys.stdout, "encoding", "") or ""
    if encoding.lower() == "utf-8":
        return

    # Try the native reconfigure API first (Python 3.7+).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
        return
    except Exception:
        pass

    # Fall back to rebuilding stdout from its underlying buffer. This path is
    # especially useful on Windows when stdout is redirected to a file and the
    # existing TextIOWrapper rejects reconfiguration.
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        try:
            sys.stdout = io.TextIOWrapper(
                buffer,
                encoding="utf-8",
                errors="strict",
                newline="\n",
            )
            return
        except Exception:
            pass

    # If even this fails, leave stdout unchanged. The caller may still specify
    # an explicit output file to guarantee UTF-8 encoding.


def _describe_image(client: OpenAI, task: _ImageTask) -> tuple[str, int, int, str]:
    b64_image = base64.b64encode(task.image_bytes).decode("ascii")
    response = _chat_completion_with_handling(
        client,
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Provide a concise yet complete description of this image. "
                            f"Respond in {task.language}."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                ],
            }
        ],
        max_tokens=200,
    )
    description = response.choices[0].message.content or ""
    return "image", task.page_index, task.order, description.strip()


def _markdown_from_table(table_data: Sequence[Sequence[str]]) -> str:
    if not table_data:
        return "(empty table)"

    headers = table_data[0]
    rows = table_data[1:]
    parts = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for row in rows:
        parts.append(" | ".join(row))
    return "\n".join(parts)


def _describe_table(client: OpenAI, task: _TableTask) -> tuple[str, int, int, str]:
    response = _chat_completion_with_handling(
        client,
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are given a table in GitHub-flavored markdown. "
                            "Summarize its contents, including notable figures, trends, "
                            "and relationships. "
                            f"Respond in {task.language}."
                        ),
                    },
                    {"type": "text", "text": task.markdown},
                ],
            }
        ],
        max_tokens=200,
    )
    description = response.choices[0].message.content or ""
    return "table", task.page_index, task.order, description.strip()


def extract_pdf_contents(pdf_path: str | Path, max_workers: int = 6) -> ExtractionResult:
    path = _ensure_pdf_path(pdf_path)
    client = OpenAI()
    image_tasks: list[_ImageTask] = []
    table_tasks: list[_TableTask] = []

    fragments_by_page: list[list[tuple[int, str]]] = []

    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc):
            page_fragments: list[tuple[int, str]] = []
            order = 0

            # -------- Extract text --------
            text = page.get_text("text").strip()
            language = _determine_language(text)
            if text:
                page_fragments.append((order, text))
                order += 1

            # -------- Extract tables safely (with textpage fix) --------
            table_markdowns: list[str] = []
            try:
                textpage = page.get_textpage()
                tables_obj = page.find_tables(textpage=textpage)
                tables = getattr(tables_obj, "tables", [])
            except Exception:
                tables = []  # fail-safe: no tables on this page

            for table in tables:
                try:
                    table_data = [[str(cell) for cell in row] for row in table.extract()]
                    if not table_data:
                        continue
                    table_markdowns.append(_markdown_from_table(table_data))
                except Exception:
                    continue  # skip malformed table safely

            # Detect language based on tables if no text
            if not text and language == "English" and table_markdowns:
                language = _determine_language("\n".join(table_markdowns))

            # -------- Extract images --------
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                image = doc.extract_image(xref)
                width = image.get("width", 0)
                height = image.get("height", 0)

                # Skip tiny images (icons, dots)
                if width * height <= 10_000:
                    continue

                image_bytes = image["image"]
                image_tasks.append(
                    _ImageTask(
                        page_index=page_index,
                        order=order,
                        image_bytes=image_bytes,
                        language=language,
                    )
                )
                order += 1

            # -------- Queue table descriptions --------
            for markdown in table_markdowns:
                table_tasks.append(
                    _TableTask(
                        page_index=page_index,
                        order=order,
                        markdown=markdown,
                        language=language,
                    )
                )
                order += 1

            fragments_by_page.append(page_fragments)

    # -------- Parallel description calls --------
    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for image_task in image_tasks:
            futures.append(
                executor.submit(_describe_image, client=client, task=image_task)
            )
        for table_task in table_tasks:
            futures.append(
                executor.submit(_describe_table, client=client, task=table_task)
            )

        for future in as_completed(futures):
            kind, page_index, order, description = future.result()
            fragments_by_page[page_index].append((order, description))

    # -------- Assemble final output --------
    items: list[str] = []
    for page_fragments in fragments_by_page:
        ordered_fragments = [
            text for _, text in sorted(page_fragments, key=lambda x: x[0])
        ]
        items.append("\n".join(filter(None, ordered_fragments)).strip())

    return ExtractionResult(items=items)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract PDF text, image descriptions, and table descriptions."
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path to write UTF-8 output instead of stdout.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=6,
        help="Maximum number of worker threads for API calls.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    
    # Ensure stdout is UTF-8 capable (helps on Windows when redirecting output).
    _best_effort_utf8_stdout()
    
    try:
        result = extract_pdf_contents(args.pdf, max_workers=args.max_workers)
    except RuntimeError as exc:
        print(exc)
        return
    
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(result.items), encoding="utf-8")
        return

    for i, item in enumerate(result.items):
        print(f"#{i}\n{item}\n\n")


if __name__ == "__main__":
    main()