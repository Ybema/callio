from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse
import mimetypes
import json
import re

import httpx
from bs4 import BeautifulSoup, Tag

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
CONTENT_TYPE_TO_EXT = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
USER_AGENT = "Mozilla/5.0 (compatible; Callio/1.0; +https://sustainovate.com)"


def _safe_filename(value: str, fallback: str = "document") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return name or fallback


def _collect_links_from_node(node: Tag, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for a in node.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        text = a.get_text(" ", strip=True)
        links.append((absolute, text))
    return links


def _extract_esa_download_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading_text = heading.get_text(" ", strip=True).lower()
        if "download" not in heading_text:
            continue

        links: list[tuple[str, str]] = []
        for sibling in heading.find_all_next():
            if sibling is not heading and sibling.name and re.match(r"^h[1-6]$", sibling.name):
                break
            if isinstance(sibling, Tag):
                links.extend(_collect_links_from_node(sibling, base_url))

        if links:
            return links
    return []


def _discover_links(call_url: str, html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(call_url)

    if "business.esa.int" in (parsed.netloc or "").lower():
        esa_links = _extract_esa_download_links(soup, call_url)
        if esa_links:
            return esa_links

    return _collect_links_from_node(soup, call_url)


def _is_candidate_download(url: str, text: str) -> bool:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in ALLOWED_EXTENSIONS:
        return True

    haystack = f"{url} {text}".lower()
    if any(marker in haystack for marker in ("download", "pdf", "docx", "guidelines", "slides")):
        return True
    return False


def _pick_filename(url: str, text: str, content_type: str | None, index: int) -> str:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        guessed = CONTENT_TYPE_TO_EXT.get((content_type or "").split(";")[0].strip().lower(), "")
        if not guessed:
            guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip().lower() or "")
        ext = guessed if guessed in ALLOWED_EXTENSIONS else ".pdf"

    stem = Path(parsed.path).name
    if stem:
        stem = Path(stem).stem
    if not stem:
        stem = text or f"document_{index}"
    return f"{_safe_filename(stem, f'document_{index}')}{ext}"


def _dedupe_target_path(target_dir: Path, filename: str) -> Path:
    candidate = target_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(2, 1000):
        next_candidate = target_dir / f"{stem}_{i}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    return target_dir / f"{stem}_{candidate.stat().st_mtime_ns}{suffix}"


def _download_index_path(target_dir: Path) -> Path:
    return target_dir / ".download_index.json"


def _load_download_index(target_dir: Path) -> dict:
    path = _download_index_path(target_dir)
    if not path.exists():
        return {"documents": {}, "updated_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"documents": {}, "updated_at": None}


def _save_download_index(target_dir: Path, data: dict) -> None:
    path = _download_index_path(target_dir)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


async def acquire_documents(
    call_url: str,
    target_dir: Path,
    max_files: int = 12,
) -> list[dict]:
    target_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    index = _load_download_index(target_dir)
    doc_idx: dict = index.setdefault("documents", {})

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        page_resp = await client.get(call_url)
        page_resp.raise_for_status()
        links = _discover_links(call_url, page_resp.text)

        seen_urls: set[str] = set()
        candidates = []
        for url, text in links:
            if url in seen_urls:
                continue
            if not _is_candidate_download(url, text):
                continue
            seen_urls.add(url)
            candidates.append((url, text))

        for idx, (doc_url, text) in enumerate(candidates[:max_files], start=1):
            try:
                existing = doc_idx.get(doc_url)
                if existing:
                    existing_filename = existing.get("filename")
                    if existing_filename and (target_dir / existing_filename).exists():
                        results.append(
                            {
                                "url": doc_url,
                                "filename": existing_filename,
                                "size_bytes": int(existing.get("size_bytes") or (target_dir / existing_filename).stat().st_size),
                                "status": "skipped_existing",
                                "error": None,
                            }
                        )
                        continue

                # Bootstrap idempotency even if index file was absent before:
                # when a deterministic filename already exists, skip redownload.
                predicted_filename = _pick_filename(doc_url, text, None, idx)
                predicted_path = target_dir / predicted_filename
                if predicted_path.exists():
                    size_bytes = predicted_path.stat().st_size
                    doc_idx[doc_url] = {
                        "filename": predicted_filename,
                        "size_bytes": size_bytes,
                    }
                    results.append(
                        {
                            "url": doc_url,
                            "filename": predicted_filename,
                            "size_bytes": size_bytes,
                            "status": "skipped_existing",
                            "error": None,
                        }
                    )
                    continue

                resp = await client.get(doc_url)
                status = int(resp.status_code)
                if status >= 400:
                    results.append(
                        {
                            "url": doc_url,
                            "filename": None,
                            "size_bytes": None,
                            "status": "error",
                            "error": f"http_{status}",
                        }
                    )
                    continue

                content_type = resp.headers.get("content-type", "")
                filename = _pick_filename(doc_url, text, content_type, idx)
                path = _dedupe_target_path(target_dir, filename)
                path.write_bytes(resp.content)
                doc_idx[doc_url] = {
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                }
                results.append(
                    {
                        "url": doc_url,
                        "filename": path.name,
                        "size_bytes": path.stat().st_size,
                        "status": "downloaded",
                        "error": None,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "url": doc_url,
                        "filename": None,
                        "size_bytes": None,
                        "status": "error",
                        "error": str(exc),
                    }
                )

    _save_download_index(target_dir, index)
    return results
