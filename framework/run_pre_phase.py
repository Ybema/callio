#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-Phase: Document Processing and Preparation

WHAT THIS SCRIPT DOES:
======================
This script prepares all your documents for analysis by converting them to markdown format.
It's the first step you should run before starting any phase of the proposal framework.

STEP 1: DOCUMENT DISCOVERY
- Finds PDF and Word documents in input folders
- Locates call documents, strategy documents, and templates
- Identifies files that need processing

STEP 2: DOCUMENT CONVERSION
- Converts PDF files to markdown using MarkItDown
- Converts Word documents to markdown with formatting
- Creates processed versions alongside original files
- Calculates file hashes for version tracking

EXTERNAL MODULES USED:
======================
- scripts/document_processor.py: Handles document conversion and processing
- MarkItDown library: Converts various file formats to markdown

USAGE:
======
python3 run_pre_phase.py [--verbose]

REQUIREMENTS:
=============
- Call documents in input/call_documents/
- Strategy documents in input/strategy_documents/

OUTPUTS:
========
- Processed markdown files (filename_processed.md)
- Processing report in output/
- Detailed logs in output/logs/
"""

import sys
import pathlib
import argparse
import logging
import time
import re
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add the scripts module to the path
sys.path.append(str(Path(__file__).parent / "scripts"))

from document_processor import DocumentProcessor
from call_context import ensure_call_dir, load_call_config, load_env_for_call, resolve_call_dir


class PrePhaseProcessor:
    """
    Handles the pre-phase document ingestion and processing.
    """
    
    def __init__(self, framework_root: Path, call_dir: Path, output_dir: Optional[Path] = None):
        """
        Initialize the pre-phase processor.
        
        Args:
            framework_root: Root directory of the project framework
            call_dir: Call-specific workspace directory
            output_dir: Optional output directory (defaults to call_dir/output)
        """
        self.framework_root = framework_root
        self.call_dir = call_dir
        self.output_dir = output_dir or call_dir / "output"
        self.processed_files = {}
        self.call_config = load_call_config(call_dir)
        self.llm_model = self.call_config.get("model", "gpt-4o-mini")
        self.synthesis_model = self.call_config.get("synthesis_model", "claude-sonnet-4-20250514")
        
        # Initialize document processor
        self.doc_processor = DocumentProcessor(
            config={"framework_root": str(framework_root)},
            reference_guides={}
        )
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for the pre-phase processor."""
        log_dir = self.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"pre_phase_{timestamp}.log"
        
        self.logger = logging.getLogger(f"pre_phase.{timestamp}")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        
        self.logger.info(f"Pre-phase processor initialized. Log file: {log_file}")

    def _manifest_path(self) -> Path:
        """Return path to pre-phase context manifest."""
        manifest_dir = self.output_dir / "pre_phase"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        return manifest_dir / ".context_manifest.json"

    def _load_manifest(self) -> Dict[str, Any]:
        """Load pre-phase manifest if present, else return default payload."""
        manifest_path = self._manifest_path()
        if not manifest_path.exists():
            return {"version": 1, "files": {}}
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"version": 1, "files": {}}
            data.setdefault("version", 1)
            data.setdefault("files", {})
            return data
        except Exception:
            self.logger.warning("Manifest unreadable; starting fresh.")
            return {"version": 1, "files": {}}

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Persist context manifest."""
        manifest_path = self._manifest_path()
        manifest["last_sync"] = datetime.now().isoformat()
        manifest.setdefault("version", 1)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def save_manifest(self, manifest: Dict[str, Any]) -> None:
        """Public manifest write helper for orchestrator context sync."""
        self._save_manifest(manifest)

    def _relative_key(self, file_path: Path) -> str:
        """Stable relative key for manifest entries."""
        return str(file_path.relative_to(self.call_dir))

    def _build_context_input_hash(self, entries: List[Dict[str, Any]]) -> str:
        """Hash the context inputs to detect if synthesis can be reused."""
        sha = hashlib.sha256()
        for entry in sorted(entries, key=lambda e: e.get("original_path", "")):
            sha.update(entry.get("document_type", "").encode("utf-8"))
            sha.update(entry.get("file_hash", "").encode("utf-8"))
            sha.update(entry.get("original_path", "").encode("utf-8"))
        return sha.hexdigest()

    def _normalize_for_dedup(self, text: str) -> str:
        """Normalize text snippets for lightweight deduplication."""
        lowered = text.lower()
        lowered = re.sub(r"#+\s*", "", lowered)
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _split_text_chunks(self, text: str, max_chars: int = 16000) -> List[str]:
        """Split large text into paragraph chunks below max_chars."""
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for block in blocks:
            candidate_len = current_len + len(block) + 2
            if current and candidate_len > max_chars:
                chunks.append("\n\n".join(current))
                current = [block]
                current_len = len(block)
            else:
                current.append(block)
                current_len = candidate_len

        if current:
            chunks.append("\n\n".join(current))

        return chunks

    def _select_relevant_call_blocks(self, markdown_content: str, max_chars: int = 60000) -> str:
        """
        Keep only likely proposal-relevant blocks before LLM summarization.
        This lowers token use and avoids spending context on boilerplate.
        """
        keywords = [
            "objective", "scope", "eligibility", "requirement", "deadline", "budget",
            "funding", "evaluation", "criterion", "impact", "outcome", "deliverable",
            "milestone", "consortium", "partner", "technology", "space", "fishing",
            "traceability", "sustainability", "implementation", "kpi", "proposal",
            "submission", "authorisation", "teb", "national delegation", "pilot",
            "proof of concept", "call for proposals", "habs", "iuu",
        ]
        keyword_regex = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)

        blocks = [b.strip() for b in re.split(r"\n\s*\n", markdown_content) if b.strip()]
        scored: List[tuple[int, str]] = []
        for block in blocks:
            score = len(keyword_regex.findall(block))
            if block.startswith("#"):
                score += 2
            if score > 0:
                scored.append((score, block))

        # Fallback: if nothing scored, keep beginning of source.
        if not scored:
            return markdown_content[:max_chars]

        scored.sort(key=lambda x: x[0], reverse=True)
        selected: List[str] = []
        seen = set()
        total = 0
        for _, block in scored:
            normalized = self._normalize_for_dedup(block)
            if not normalized or normalized in seen:
                continue
            block_len = len(block) + 2
            if total + block_len > max_chars:
                continue
            selected.append(block)
            seen.add(normalized)
            total += block_len
            if total >= max_chars:
                break

        return "\n\n".join(selected)

    def _call_llm_markdown(self, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Route to OpenAI or Anthropic based on model name."""
        model = model or self.llm_model
        if model.startswith("claude"):
            return self._call_anthropic_markdown(system_prompt, user_prompt, model)
        return self._call_openai_markdown(system_prompt, user_prompt, model)

    def _call_anthropic_markdown(self, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Call Anthropic for markdown synthesis."""
        model = model or self.synthesis_model
        try:
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0,
            )
            text = response.content[0].text if response.content else ""
            return {
                "success": True,
                "text": text.strip(),
                "usage": {
                    "prompt_tokens": getattr(response.usage, "input_tokens", 0),
                    "completion_tokens": getattr(response.usage, "output_tokens", 0),
                    "total_tokens": getattr(response.usage, "input_tokens", 0) + getattr(response.usage, "output_tokens", 0),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _call_openai_markdown(self, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Call OpenAI for markdown synthesis. Returns success/data/error."""
        try:
            from openai import OpenAI

            client = OpenAI()
            response = client.chat.completions.create(
                model=model or self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
            text = response.choices[0].message.content or ""
            usage = response.usage
            return {
                "success": True,
                "text": text.strip(),
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage, "completion_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _split_markdown_sections(self, markdown_content: str) -> List[Dict[str, str]]:
        """
        Split markdown into ordered sections while preserving heading hierarchy.
        Returns items with `heading` and `body`.
        """
        lines = markdown_content.splitlines()
        sections: List[Dict[str, str]] = []
        current_heading = "# Document Overview"
        current_body: List[str] = []

        for line in lines:
            if re.match(r"^#{1,6}\s+", line):
                if current_body:
                    sections.append(
                        {
                            "heading": current_heading,
                            "body": "\n".join(current_body).strip(),
                        }
                    )
                current_heading = line.strip()
                current_body = []
            else:
                current_body.append(line)

        if current_body:
            sections.append(
                {
                    "heading": current_heading,
                    "body": "\n".join(current_body).strip(),
                }
            )

        return [s for s in sections if s["body"]]

    def _extract_document_facts(self, markdown_content: str, source_name: str) -> tuple[str, Dict[str, Any]]:
        """
        Pass 1: Extract all concrete, proposal-relevant facts from a single source
        document as a flat structured bullet list.  Cleans OCR noise, removes
        boilerplate, but preserves every actionable detail.

        Returns (extracted_markdown, metadata_dict).
        """
        # Chunk large documents so each LLM call stays under context limits.
        max_chunk_chars = 50000
        content = markdown_content[:120000]
        chunks = self._split_text_chunks(content, max_chars=max_chunk_chars)

        system_prompt = (
            "You are a senior funding-call analyst performing EXHAUSTIVE fact extraction.\n"
            "Your task: extract EVERY concrete, proposal-relevant fact from the source text.\n\n"
            "Output a structured markdown document with topic headings and detailed bullets.\n"
            "Choose headings that fit the content (e.g. Call Overview, Eligibility, Budget, "
            "Timeline, Technical Scope, Use Cases, Evaluation Criteria, Submission Process, etc.).\n\n"
            "CRITICAL — extraction ratio guidance:\n"
            "- Your output should be 40-70% the length of the input text.\n"
            "- You are cleaning and restructuring, NOT summarizing. Do not compress aggressively.\n\n"
            "Rules:\n"
            "- Extract ALL specific facts: names, organisations, numbers, dates, deadlines, "
            "thresholds, percentages, constraints, technical requirements, evaluation weights, "
            "definitions, process steps, conditions, exceptions, and qualifications.\n"
            "- Preserve explanatory context that gives meaning to facts (e.g. WHY a requirement "
            "exists, WHAT constitutes compliance, HOW a process works step-by-step).\n"
            "- Preserve definitions and descriptions of concepts, categories, and terms.\n"
            "- Fix OCR artefacts (broken words, stray whitespace, garbled characters) silently.\n"
            "- Remove ONLY: page headers/footers, watermarks, table of contents, and document "
            "metadata boilerplate. Everything else stays.\n"
            "- Do NOT add interpretation, advice, or commentary — only facts from the source.\n"
            "- Do NOT invent information. If something is unclear, include it with '[unclear in source]'.\n"
            "- When in doubt, INCLUDE the detail. Over-extraction is always better than under-extraction.\n"
            "- Use sub-bullets for related details and nested requirements.\n"
        )

        chunk_extracts: List[str] = []
        total_tokens = 0
        api_calls = 0

        for i, chunk in enumerate(chunks, 1):
            user_prompt = (
                f"Source: {source_name}\n"
                f"Chunk {i}/{len(chunks)}\n\n"
                "Extract all proposal-relevant facts from this text:\n\n"
                f"{chunk}"
            )
            llm_result = self._call_llm_markdown(system_prompt, user_prompt)
            if not llm_result.get("success"):
                self.logger.warning(
                    f"Fact extraction failed for {source_name} chunk {i}: {llm_result.get('error')}"
                )
                return markdown_content, {
                    "llm_optimized": False,
                    "reason": "llm_failed",
                    "error": llm_result.get("error", "unknown"),
                }
            extracted = llm_result["text"].strip()
            # Guardrail: if extraction is suspiciously short vs source, flag it
            if len(extracted) < max(500, int(len(chunk) * 0.25)):
                self.logger.warning(
                    f"Extraction for {source_name} chunk {i} seems thin "
                    f"({len(extracted)} chars from {len(chunk)} chars source). Keeping anyway."
                )
            chunk_extracts.append(extracted)
            usage = llm_result.get("usage", {})
            total_tokens += usage.get("total_tokens", 0)
            api_calls += 1

        if not chunk_extracts:
            return markdown_content, {
                "llm_optimized": False,
                "reason": "no_content",
            }

        combined = "\n\n".join(chunk_extracts)
        wrapped = (
            f"# {source_name} — Extracted Facts\n\n"
            f"{combined.strip()}\n"
        )
        return wrapped, {
            "llm_optimized": True,
            "model": self.llm_model,
            "input_chars": len(markdown_content),
            "output_chars": len(wrapped),
            "chunks": len(chunks),
            "api_calls": api_calls,
            "total_tokens": total_tokens,
        }

    def _build_compiled_call_context(
        self,
        call_processed_entries: List[Dict[str, Any]],
        strategy_processed_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Pass 2: Synthesize all per-document extracts into a single unified call
        context document, organized by topic (not by source), with full semantic
        deduplication done by the LLM.
        """
        strategy_processed_entries = strategy_processed_entries or []
        if not call_processed_entries and not strategy_processed_entries:
            return None

        context_dir = self.output_dir / "pre_phase" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        context_path = context_dir / f"call_context_compiled_{timestamp}.md"

        # Collect all per-document extracts
        source_texts: List[str] = []
        source_names: List[str] = []
        total_input_chars = 0
        for entry in call_processed_entries:
            path = Path(entry["markdown_path"])
            text = path.read_text(encoding="utf-8", errors="ignore")
            source_texts.append(text)
            source_names.append(f"CALL::{path.stem}")
            total_input_chars += len(text)

        for entry in strategy_processed_entries:
            path = Path(entry["markdown_path"])
            text = path.read_text(encoding="utf-8", errors="ignore")
            source_texts.append(
                f"# Strategy Source: {path.stem}\n\n{text.strip()}\n"
            )
            source_names.append(f"STRATEGY::{path.stem}")
            total_input_chars += len(text)

        combined_extracts = "\n\n---\n\n".join(source_texts)

        # If combined text is small enough, do a single synthesis call.
        # Otherwise chunk and do incremental merging.
        max_synthesis_input = 100000

        system_prompt = (
            "You are a senior funding-call analyst compiling a unified reference document.\n\n"
            "You receive source material from two categories:\n"
            "1) official funding call documents\n"
            "2) project strategy documents from the proposal team.\n"
            "Your task: merge them into ONE comprehensive, deduplicated markdown document.\n\n"
            "Structure the output by TOPIC, not by source document. Use clear markdown headings.\n"
            "Suggested sections (adapt to fit the content):\n"
            "- Call Overview (name, issuer, programme, type)\n"
            "- Objectives & Scope\n"
            "- Technical Requirements & Use Cases\n"
            "- Eligibility & Consortium Requirements\n"
            "- Budget & Funding Structure\n"
            "- Timeline & Deadlines\n"
            "- Submission Process & Requirements\n"
            "- Evaluation Criteria\n"
            "- Key Definitions & Terminology\n\n"
            "When strategy sources are present, include a dedicated section:\n"
            "- Project Strategy & Constraints\n\n"
            "Rules:\n"
            "- DEDUPLICATE: when multiple sources state the same fact, include it once.\n"
            "- PRESERVE ALL DETAILS: every concrete fact, number, date, name, constraint must appear.\n"
            "- When sources conflict, note the conflict explicitly.\n"
            "- Keep official call requirements clearly separate from project strategy.\n"
            "- Do NOT add interpretation, strategy advice, or commentary beyond source text.\n"
            "- Do NOT invent information.\n"
            "- Use sub-bullets for related details.\n"
            "- The output must be self-contained — a reader should understand the full call without seeing the sources.\n"
        )

        if len(combined_extracts) <= max_synthesis_input:
            user_prompt = (
                f"Sources: {', '.join(source_names)}\n\n"
                "Merge the following extracts into a single unified call context document:\n\n"
                f"{combined_extracts}"
            )
            llm_result = self._call_llm_markdown(system_prompt, user_prompt, model=self.synthesis_model)
        else:
            # Incremental merge: process sources in batches
            self.logger.info("Combined extracts exceed single-call limit, using incremental merge...")
            merged_so_far = ""
            llm_result = {"success": True, "text": "", "usage": {"total_tokens": 0}}

            for i, text in enumerate(source_texts):
                if merged_so_far:
                    user_prompt = (
                        "Current merged document:\n\n"
                        f"{merged_so_far[:max_synthesis_input // 2]}\n\n"
                        "---\n\n"
                        f"New source to integrate: {source_names[i]}\n\n"
                        f"{text[:max_synthesis_input // 2]}\n\n"
                        "Produce an updated merged document incorporating the new source. "
                        "Deduplicate and reorganize by topic."
                    )
                else:
                    user_prompt = (
                        f"Source: {source_names[i]}\n\n"
                        "Organize these extracts into a unified call context document:\n\n"
                        f"{text[:max_synthesis_input]}"
                    )

                step_result = self._call_llm_markdown(system_prompt, user_prompt, model=self.synthesis_model)
                if not step_result.get("success"):
                    llm_result = step_result
                    break
                merged_so_far = step_result["text"]
                step_usage = step_result.get("usage", {})
                llm_result["usage"]["total_tokens"] = (
                    llm_result["usage"].get("total_tokens", 0)
                    + step_usage.get("total_tokens", 0)
                )

            if llm_result.get("success", True) and merged_so_far:
                llm_result["text"] = merged_so_far
                llm_result["success"] = True

        if not llm_result.get("success"):
            self.logger.warning(
                f"LLM synthesis failed: {llm_result.get('error')}. "
                "Falling back to concatenation."
            )
            content = f"# Compiled Call Context\n\n{combined_extracts}\n"
            context_path.write_text(content, encoding="utf-8")
            return {
                "path": str(context_path),
                "source_documents": len(call_processed_entries) + len(strategy_processed_entries),
                "compiled_chars": len(content),
                "synthesis": "fallback_concat",
            }

        synthesized = llm_result["text"].strip()
        header = (
            f"# Unified Call Context\n\n"
            f"_Synthesized from {len(source_names)} sources: {', '.join(source_names)}_\n"
            f"_Extraction model: `{self.llm_model}` | Synthesis model: `{self.synthesis_model}` | Generated: {timestamp}_\n\n"
        )
        content = header + synthesized + "\n"
        context_path.write_text(content, encoding="utf-8")

        usage = llm_result.get("usage", {})
        return {
            "path": str(context_path),
            "source_documents": len(call_processed_entries) + len(strategy_processed_entries),
            "input_chars": total_input_chars,
            "compiled_chars": len(content),
            "synthesis": "llm",
            "total_tokens": usage.get("total_tokens", 0),
        }
    
    def discover_static_files(self) -> Dict[str, List[Path]]:
        """
        Discover all static files that need to be processed.
        
        Returns:
            Dictionary mapping file categories to lists of file paths
        """
        static_files = {
            "call_documents": [],
            "strategy_documents": [],
        }
        
        # Call documents
        call_docs_dir = self.call_dir / "input" / "call_documents"
        if call_docs_dir.exists():
            for file_path in call_docs_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() in ['.pdf', '.docx', '.doc', '.md', '.txt'] and
                    not file_path.name.endswith('_processed.md')):
                    static_files["call_documents"].append(file_path)
        
        # Strategy documents
        strategy_docs_dir = self.call_dir / "input" / "strategy_documents"
        if strategy_docs_dir.exists():
            for file_path in strategy_docs_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() in ['.pdf', '.docx', '.doc', '.md', '.txt'] and
                    not file_path.name.endswith('_processed.md')):
                    static_files["strategy_documents"].append(file_path)
        
        return static_files
    
    def process_static_files(
        self,
        static_files: Dict[str, List[Path]],
        manifest: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process all discovered static files and convert them to markdown.
        
        Args:
            static_files: Dictionary of file categories and their paths
            
        Returns:
            Dictionary containing processing results
        """
        manifest = manifest or {"version": 1, "files": {}}
        manifest_files = manifest.get("files", {})
        current_keys = {
            self._relative_key(path)
            for files in static_files.values()
            for path in files
        }

        results = {
            "success": True,
            "processed_files": {},
            "errors": [],
            "summary": {},
            "manifest": manifest,
            "changed_inputs": False,
        }
        
        total_files = sum(len(files) for files in static_files.values())
        processed_count = 0
        
        self.logger.info(f"Starting processing of {total_files} static files...")
        
        for category, file_paths in static_files.items():
            self.logger.info(f"Processing {category}: {len(file_paths)} files")
            results["processed_files"][category] = []
            
            for file_path in file_paths:
                try:
                    processed_count += 1
                    self.logger.info(f"[{processed_count}/{total_files}] Processing: {file_path.name}")
                    
                    # Determine document type based on category
                    doc_type = self._get_document_type(category, file_path)
                    file_hash = self.doc_processor._calculate_file_hash(file_path)
                    rel_key = self._relative_key(file_path)
                    existing = manifest_files.get(rel_key, {})
                    existing_md = existing.get("processed_md")
                    existing_md_path = self.call_dir / existing_md if existing_md else None

                    if (
                        existing.get("hash") == file_hash
                        and existing_md_path
                        and existing_md_path.exists()
                    ):
                        self.logger.info(f"✓ Unchanged, skipping conversion: {file_path.name}")
                        file_result = {
                            "original_path": str(file_path),
                            "markdown_path": str(existing_md_path),
                            "document_type": doc_type,
                            "file_hash": file_hash,
                            "processed_at": existing.get("processed_at"),
                            "processing_method": existing.get("processing_method", "cached"),
                            "call_extracted": existing.get("call_extracted", False),
                            "extraction_metadata": existing.get("extraction_metadata", {}),
                            "llm_optimization": existing.get("llm_optimization"),
                            "cached": True,
                        }
                        results["processed_files"][category].append(file_result)
                        continue
                    
                    # Process the document
                    result = self.doc_processor.process_document(file_path, doc_type)
                    
                    if result["success"]:
                        markdown_content = result["markdown"]
                        llm_optimization: Optional[Dict[str, Any]] = None
                        if doc_type == "call_document":
                            markdown_content, llm_optimization = self._extract_document_facts(
                                markdown_content, file_path.name
                            )

                        # Save markdown version in the same directory
                        markdown_path = self._save_markdown_version(file_path, markdown_content)
                        
                        # Store processing result
                        file_result = {
                            "original_path": str(file_path),
                            "markdown_path": str(markdown_path),
                            "document_type": doc_type,
                            "file_hash": result.get("file_hash") or file_hash,
                            "word_count": result.get("structured_content", {}).get("word_count", 0),
                            "sections": len(result.get("structured_content", {}).get("sections", [])),
                            "processed_at": result.get("processed_at"),
                            "processing_method": result.get("processing_method"),
                            "call_extracted": result.get("call_extracted", False),
                            "extraction_metadata": result.get("extraction_metadata", {})
                        }
                        if llm_optimization is not None:
                            file_result["llm_optimization"] = llm_optimization
                        
                        results["processed_files"][category].append(file_result)
                        results["changed_inputs"] = True
                        manifest_files[rel_key] = {
                            "hash": file_result.get("file_hash"),
                            "processed_md": str(Path(markdown_path).relative_to(self.call_dir)),
                            "category": doc_type,
                            "processed_at": file_result.get("processed_at"),
                            "processing_method": file_result.get("processing_method"),
                            "call_extracted": file_result.get("call_extracted", False),
                            "extraction_metadata": file_result.get("extraction_metadata", {}),
                            "llm_optimization": file_result.get("llm_optimization"),
                        }
                        
                        if doc_type == "call_document":
                            if result.get("call_extracted"):
                                extraction_meta = result.get("extraction_metadata", {})
                                compression_ratio = extraction_meta.get("compression_ratio", 0)
                                self.logger.info(f"✓ Successfully processed with call extraction: {file_path.name}")
                                self.logger.info(f"  → Extracted {extraction_meta.get('extracted_length', 0):,} chars from {extraction_meta.get('original_length', 0):,} chars (ratio: {compression_ratio:.3f})")
                            else:
                                self.logger.warning(f"✓ Processed but call extraction failed: {file_path.name}")
                            if llm_optimization and llm_optimization.get("llm_optimized"):
                                self.logger.info(
                                    "  → Facts extracted: "
                                    f"{llm_optimization.get('input_chars', 0):,} → "
                                    f"{llm_optimization.get('output_chars', 0):,} chars "
                                    f"({llm_optimization.get('chunks', 0)} chunks, "
                                    f"{llm_optimization.get('api_calls', 0)} calls, "
                                    f"{llm_optimization.get('total_tokens', 0):,} tokens)"
                                )
                        else:
                            self.logger.info(f"✓ Successfully processed: {file_path.name}")
                        
                    else:
                        error_msg = f"Failed to process {file_path.name}: {result.get('error', 'Unknown error')}"
                        results["errors"].append(error_msg)
                        self.logger.error(f"✗ {error_msg}")
                        
                except Exception as e:
                    error_msg = f"Exception processing {file_path.name}: {str(e)}"
                    results["errors"].append(error_msg)
                    self.logger.error(f"✗ {error_msg}")

        removed_keys = [k for k in list(manifest_files.keys()) if k not in current_keys]
        if removed_keys:
            results["changed_inputs"] = True
            for key in removed_keys:
                entry = manifest_files.get(key, {})
                md_rel = entry.get("processed_md")
                if md_rel:
                    md_path = self.call_dir / md_rel
                    if md_path.exists():
                        try:
                            md_path.unlink()
                        except Exception:
                            self.logger.warning(f"Could not remove stale processed file: {md_path}")
                manifest_files.pop(key, None)
        
        # Generate summary
        results["summary"] = {
            "total_files": total_files,
            "successfully_processed": sum(len(files) for files in results["processed_files"].values()),
            "errors": len(results["errors"]),
            "categories_processed": len([cat for cat, files in results["processed_files"].items() if files])
        }

        all_context_entries = (
            results["processed_files"].get("call_documents", [])
            + results["processed_files"].get("strategy_documents", [])
        )
        input_hash = self._build_context_input_hash(all_context_entries) if all_context_entries else ""
        compiled_context = None
        existing_compiled_rel = manifest.get("compiled_context_path")
        existing_compiled = self.call_dir / existing_compiled_rel if existing_compiled_rel else None

        if (
            all_context_entries
            and manifest.get("compiled_context_input_hash") == input_hash
            and existing_compiled
            and existing_compiled.exists()
        ):
            compiled_context = {
                "path": str(existing_compiled),
                "source_documents": len(all_context_entries),
                "compiled_chars": len(existing_compiled.read_text(encoding="utf-8", errors="ignore")),
                "synthesis": "cached",
            }
            self.logger.info("Context inputs unchanged; reusing existing compiled call context.")
        elif all_context_entries:
            compiled_context = self._build_compiled_call_context(
                results["processed_files"].get("call_documents", []),
                results["processed_files"].get("strategy_documents", []),
            )

        if compiled_context:
            results["compiled_call_context"] = compiled_context
            self.logger.info(
                "Synthesized unified call context: "
                f"{Path(compiled_context['path']).name} "
                f"({compiled_context['source_documents']} sources, "
                f"{compiled_context['compiled_chars']:,} chars, "
                f"method: {compiled_context.get('synthesis', 'unknown')})"
            )
            manifest["compiled_context_path"] = str(Path(compiled_context["path"]).relative_to(self.call_dir))
            manifest["compiled_context_input_hash"] = input_hash
            manifest["compiled_generated_at"] = datetime.now().isoformat()
        else:
            manifest.pop("compiled_context_path", None)
            manifest.pop("compiled_context_input_hash", None)
            manifest.pop("compiled_generated_at", None)
        
        if results["errors"]:
            results["success"] = False
        
        self.logger.info(f"Processing complete. Summary: {results['summary']}")
        return results
    
    def _get_document_type(self, category: str, file_path: Path) -> str:
        """
        Determine the document type based on category and file path.
        
        Args:
            category: File category
            file_path: Path to the file
            
        Returns:
            Document type string
        """
        if category == "call_documents":
            return "call_document"
        elif category == "strategy_documents":
            return "strategy_document"
        else:
            return "unknown"
    
    def _save_markdown_version(self, original_path: Path, markdown_content: str) -> Path:
        """
        Save the markdown version of a processed file.
        Overwrites existing files if they already exist.
        
        Args:
            original_path: Original file path
            markdown_content: Markdown content to save
            
        Returns:
            Path to the saved markdown file
        """
        # Create markdown filename
        markdown_filename = original_path.stem + "_processed.md"
        markdown_path = original_path.parent / markdown_filename
        
        # Check if file already exists and log the action
        if markdown_path.exists():
            self.logger.info(f"Overwriting existing file: {markdown_path.name}")
        
        # Write markdown content (overwrites if exists)
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return markdown_path
    
    def save_processing_report(self, results: Dict[str, Any]) -> Path:
        """
        Save a processing report with all results.
        Overwrites existing report files if they already exist.
        
        Args:
            results: Processing results dictionary
            
        Returns:
            Path to the saved report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / "pre_phase" / "conversion_logs" / f"document_conversion_log_{timestamp}.json"
        
        # Check if report file already exists and log the action
        if report_path.exists():
            self.logger.info(f"Overwriting existing report file: {report_path.name}")
        
        # Add metadata to results
        results["metadata"] = {
            "framework_root": str(self.framework_root),
            "call_dir": str(self.call_dir),
            "output_dir": str(self.output_dir),
            "processed_at": datetime.now().isoformat(),
            "processor_version": "1.0.0"
        }
        
        import json
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Processing report saved: {report_path}")
        return report_path
    
    def run(self) -> bool:
        """
        Run the complete pre-phase processing.
        
        Returns:
            True if processing was successful, False otherwise
        """
        try:
            overall_start = time.time()
            self.logger.info("Starting pre-phase processing...")
            
            # Discover static files
            step_start = time.time()
            static_files = self.discover_static_files()
            manifest = self._load_manifest()
            discovery_time = time.time() - step_start
            print(f"⏱️  Document discovery completed in {discovery_time:.2f}s")
            self.logger.info(f"⏱️  Document discovery completed in {discovery_time:.2f}s")
            
            if not any(static_files.values()):
                self.logger.warning("No static files found to process")
                return True
            
            # Process all static files
            step_start = time.time()
            results = self.process_static_files(static_files, manifest=manifest)
            processing_time = time.time() - step_start
            print(f"⏱️  Document processing completed in {processing_time:.2f}s")
            self.logger.info(f"⏱️  Document processing completed in {processing_time:.2f}s")
            self._save_manifest(results.get("manifest", manifest))
            
            # Save processing report
            step_start = time.time()
            report_path = self.save_processing_report(results)
            report_time = time.time() - step_start
            print(f"⏱️  Report generation completed in {report_time:.2f}s")
            self.logger.info(f"⏱️  Report generation completed in {report_time:.2f}s")
            
            # Log final status with total time
            overall_time = time.time() - overall_start
            if results["success"]:
                self.logger.info("✓ Pre-phase processing completed successfully")
                print(f"⏱️  TOTAL PRE-PHASE TIME: {overall_time:.2f}s")
                self.logger.info(f"⏱️  TOTAL PRE-PHASE TIME: {overall_time:.2f}s")
                self.logger.info(f"Report saved: {report_path}")
            else:
                self.logger.error("✗ Pre-phase processing completed with errors")
                self.logger.error(f"Errors: {results['errors']}")
            
            return results["success"]
            
        except Exception as e:
            self.logger.error(f"Fatal error in pre-phase processing: {str(e)}")
            return False


def main(argv=None):
    """Main entry point for the pre-phase processor."""
    parser = argparse.ArgumentParser(
        description="Pre-Phase Document Ingestion and Processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_pre_phase.py --call my-call
  python3 run_pre_phase.py --framework-root /path/to/project framework
  python3 run_pre_phase.py --output-dir /path/to/output
        """
    )
    
    parser.add_argument(
        "--call",
        required=True,
        help="Call workspace name under framework-root/calls/"
    )

    parser.add_argument(
        "--framework-root",
        type=Path,
        default=Path(__file__).parent,
        help="Root directory of the project framework (default: script directory)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for reports (default: calls/<call>/output)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args(argv)
    
    # Validate framework root
    if not args.framework_root.exists():
        print(f"Error: Framework root directory does not exist: {args.framework_root}")
        return 1

    call_dir = resolve_call_dir(args.framework_root, args.call)
    try:
        ensure_call_dir(call_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    load_env_for_call(call_dir, args.framework_root)
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize and run processor
    processor = PrePhaseProcessor(
        framework_root=args.framework_root,
        call_dir=call_dir,
        output_dir=args.output_dir
    )
    
    success = processor.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
