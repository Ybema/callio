#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase A: LFA Document Processing and Analysis

WHAT THIS SCRIPT DOES:
======================
This script processes your Logic Framework Analysis (LFA) documents and evaluates them
against the funding call requirements. It's the first step in preparing your proposal.

STEP 1: DOCUMENT PROCESSING
- Finds Word documents in input/lfa_documents/
- Converts them to markdown format for analysis
- Creates versioned copies with timestamps
- Tracks all changes for audit purposes

STEP 2: LFA EVALUATION  
- Compares your LFA against the funding call requirements
- Checks if objectives align with call goals
- Verifies internal logic and consistency
- Evaluates writing quality and clarity
- Generates scores and improvement suggestions

EXTERNAL MODULES USED:
======================
- scripts/document_processor.py: Handles Word-to-markdown conversion
- scripts/version_control.py: Manages file versions and snapshots  
- scripts/review_engine/review_engine.py: Performs the LFA evaluation
- scripts/review_engine/prompts/: Contains evaluation criteria and prompts

USAGE:
======
python3 run_phase_a.py [--verbose]

REQUIREMENTS:
=============
- OpenAI API key in .env file
- LFA documents in input/lfa_documents/
- Call documents from pre-phase in input/call_documents/

OUTPUTS:
========
- Processed LFA files in input/lfa_documents/
- Evaluation reports in output/
- Detailed logs in output/logs/
"""

import sys
import pathlib
import argparse
import logging
import json
import time
import yaml
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add the scripts module to the path
sys.path.append(str(Path(__file__).parent / "scripts"))

from document_processor import DocumentProcessor
from version_control import VersionControl
from call_context import ensure_call_dir, load_call_config, load_env_for_call, resolve_call_dir
from lfa_restructure import restructure_lfa


# =============================================================================
# SECTION 1: LFA DOCUMENT PROCESSING
# =============================================================================
# This section handles the discovery, processing, and versioning of LFA documents.
# It converts Word documents to markdown with timestamp-based version control
# and creates comprehensive snapshots for traceability.
# 
# Key Components:
# - Document discovery in input/lfa_documents/
# - MarkItDown conversion to markdown
# - Timestamp-based versioning (YYYYMMDD_HHMMSS)
# - Version control snapshots
# - Processing reports and logging
# =============================================================================

class PhaseAProcessor:
    """
    Handles Phase A LFA document processing with version control.
    
    This class orchestrates the complete Phase A workflow:
    1. Discovers LFA documents from input directory
    2. Processes Word documents to markdown with MarkItDown
    3. Implements smart version control (content-based deduplication)
    4. Creates comprehensive snapshots for audit trail
    5. Initiates LFA analysis using the new structured review engine
    
    The processor maintains full traceability through:
    - Timestamp-based versioning (YYYYMMDD_HHMMSS)
    - Content hash tracking for deduplication
    - Comprehensive logging and error handling
    - Snapshot creation for reproducibility
    
    Attributes:
        framework_root (Path): Root directory of the project framework
        output_dir (Path): Output directory for reports and snapshots
        session_id (str): Unique session identifier for traceability
        doc_processor (DocumentProcessor): MarkItDown document processor
        version_control (VersionControl): Snapshot and version management
        logger (Logger): Configured logger for this session
    """
    
    def __init__(
        self,
        framework_root: Path,
        call_dir: Path,
        call_config: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize the Phase A processor.
        
        Args:
            framework_root: Root directory of the project framework
            call_dir: Call-specific workspace directory
            call_config: Parsed call.yaml configuration
            output_dir: Optional output directory (defaults to call_dir/output)
        """
        self.framework_root = framework_root
        self.call_dir = call_dir
        self.call_config = call_config
        self.output_dir = output_dir or call_dir / "output"
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize document processor
        self.doc_processor = DocumentProcessor(
            config={"framework_root": str(framework_root)},
            reference_guides={}
        )
        
        # Initialize version control
        self.version_control = VersionControl(self.output_dir / "snapshots")
        self.lfa_template_markdown = (
            self.framework_root / "templates" / "input_templates" / "lfa_template.md"
        )
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for the Phase A processor."""
        log_dir = self.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"phase_a_{timestamp}.log"
        
        self.logger = logging.getLogger(f"phase_a.{self.session_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        
        self.logger.info(f"Phase A processor initialized. Session ID: {self.session_id}")
        self.logger.info(f"Log file: {log_file}")
    
    # -------------------------------------------------------------------------
    # LFA DOCUMENT DISCOVERY
    # -------------------------------------------------------------------------
    # Finds all Word documents in the input/lfa_documents/ directory
    # Excludes already processed files to avoid duplication
    # Returns list of document paths ready for processing
    # -------------------------------------------------------------------------
    
    def discover_lfa_documents(self) -> List[Path]:
        """
        Discover LFA documents in the input/lfa_documents/ directory.
        
        This method scans the input directory for Word documents (.docx, .doc) that
        haven't been processed yet (excludes files ending with '_processed.md').
        
        The discovery process:
        1. Checks if input/lfa_documents/ directory exists
        2. Filters for Word document formats (.docx, .doc)
        3. Excludes already processed files to avoid duplication
        4. Logs discovered documents for transparency
        
        Returns:
            List[Path]: List of LFA document file paths ready for processing
            
        Note:
            Only discovers unprocessed documents. Already processed files
            (ending with '_processed.md') are excluded to prevent reprocessing.
        """
        lfa_docs = []
        lfa_docs_dir = self.call_dir / "input" / "lfa_documents"
        
        if not lfa_docs_dir.exists():
            self.logger.warning(f"LFA documents directory not found: {lfa_docs_dir}")
            return lfa_docs
        
        for file_path in lfa_docs_dir.iterdir():
            if (file_path.is_file() and 
                file_path.suffix.lower() in ['.docx', '.doc'] and
                not file_path.name.endswith('_processed.md')):
                lfa_docs.append(file_path)
        
        self.logger.info(f"Discovered {len(lfa_docs)} LFA documents")
        for doc in lfa_docs:
            self.logger.info(f"  - {doc.name}")
        
        return lfa_docs
    
    # -------------------------------------------------------------------------
    # LFA DOCUMENT PROCESSING
    # -------------------------------------------------------------------------
    # Converts Word documents to markdown using MarkItDown
    # Creates versioned output files with timestamps
    # Extracts structured content and metadata
    # Handles errors gracefully and provides detailed logging
    # -------------------------------------------------------------------------
    
    def process_lfa_documents(self, lfa_documents: List[Path]) -> Dict[str, Any]:
        """
        Process LFA documents and convert them to markdown with version control.
        
        This method orchestrates the complete document processing workflow:
        1. Converts Word documents to markdown using MarkItDown
        2. Implements smart version control with content-based deduplication
        3. Extracts structured content and metadata
        4. Handles errors gracefully with detailed logging
        5. Creates comprehensive processing reports
        
        The processing includes:
        - MarkItDown conversion for high-quality markdown output
        - Content hash calculation for deduplication
        - Timestamp-based versioning (YYYYMMDD_HHMMSS)
        - Metadata extraction (word count, sections, file size)
        - Error handling and recovery
        
        Args:
            lfa_documents (List[Path]): List of LFA document file paths to process
            
        Returns:
            Dict[str, Any]: Processing results containing:
                - success (bool): Overall processing success status
                - processed_documents (dict): Details of successfully processed documents
                - errors (list): List of error messages for failed documents
                - summary (dict): Processing summary statistics
                
        Note:
            Documents with identical content will have their version numbers updated
            rather than creating duplicate files, ensuring efficient storage.
        """
        results = {
            "success": True,
            "processed_documents": {},
            "errors": [],
            "summary": {}
        }
        
        if not lfa_documents:
            self.logger.warning("No LFA documents found to process")
            return results
        
        self.logger.info(f"Starting processing of {len(lfa_documents)} LFA documents...")
        
        for i, file_path in enumerate(lfa_documents, 1):
            try:
                self.logger.info(f"[{i}/{len(lfa_documents)}] Processing: {file_path.name}")
                
                # Process the document
                result = self.doc_processor.process_document(file_path, "lfa_document")
                
                if result["success"]:
                    raw_markdown = result["markdown"]
                    mapped_markdown, mapping_report = self._map_lfa_to_template_with_report(
                        raw_markdown
                    )

                    # Create versioned markdown file
                    markdown_path = self._create_versioned_markdown(file_path, mapped_markdown)
                    
                    # Save raw markdown for restructuring (before template mapping)
                    raw_path = markdown_path.parent / f"{file_path.stem}_raw.md"
                    raw_path.write_text(raw_markdown, encoding="utf-8")
                    
                    # Store processing result
                    doc_result = {
                        "original_path": str(file_path),
                        "markdown_path": str(markdown_path),
                        "raw_markdown_path": str(raw_path),
                        "document_type": "lfa_document",
                        "file_hash": result.get("file_hash"),
                        "file_size": result.get("file_size"),
                        "word_count": result.get("structured_content", {}).get("word_count", 0),
                        "sections": len(result.get("structured_content", {}).get("sections", [])),
                        "processed_at": result.get("processed_at"),
                        "version": self._extract_version_from_path(markdown_path),
                        "template_mapping": mapping_report
                    }
                    
                    results["processed_documents"][file_path.stem] = doc_result
                    self.logger.info(f"✓ Successfully processed: {file_path.name}")
                    self.logger.info(f"  → Versioned markdown: {markdown_path.name}")
                    self.logger.info(
                        "  → Template mapping coverage: "
                        f"{mapping_report.get('matched_count', 0)}/"
                        f"{mapping_report.get('template_sections_count', 0)} sections"
                    )
                    
                else:
                    error_msg = f"Failed to process {file_path.name}: {result.get('error', 'Unknown error')}"
                    results["errors"].append(error_msg)
                    self.logger.error(f"✗ {error_msg}")
                    
            except Exception as e:
                error_msg = f"Exception processing {file_path.name}: {str(e)}"
                results["errors"].append(error_msg)
                self.logger.error(f"✗ {error_msg}")
        
        # Generate summary
        results["summary"] = {
            "total_documents": len(lfa_documents),
            "successfully_processed": len(results["processed_documents"]),
            "errors": len(results["errors"]),
            "session_id": self.session_id
        }
        
        if results["errors"]:
            results["success"] = False
        
        self.logger.info(f"LFA processing complete. Summary: {results['summary']}")
        return results

    def _extract_sections(self, markdown_content: str) -> Dict[str, str]:
        """Extract markdown sections keyed by normalized heading text."""
        sections: Dict[str, List[str]] = {}
        current_key = None

        for line in markdown_content.splitlines():
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
                key = self._normalize_heading(heading)
                current_key = key
                if key not in sections:
                    sections[key] = []
            elif current_key is not None:
                sections[current_key].append(line)

        return {k: "\n".join(v).strip() for k, v in sections.items()}

    def _normalize_heading(self, heading: str) -> str:
        """Normalize heading text for robust matching."""
        return re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip()

    def _resolve_template_match(
        self, template_key: str, source_sections: Dict[str, str]
    ) -> Optional[str]:
        """Resolve the most relevant source section for a template heading."""
        aliases = {
            "background": ["background", "problem", "context"],
            "overall goal": ["overall goal", "goal", "impact"],
            "project purpose": ["project purpose", "purpose", "objective"],
            "project outcomes": ["project outcomes", "outcome", "outcomes"],
            "project approach": ["project approach", "approach", "methodology", "strategy"],
            "expected outputs results": ["expected outputs", "outputs", "results", "deliverables"],
            "activities and required inputs": ["activities", "inputs", "work plan", "tasks", "resources"],
        }

        candidate_terms = aliases.get(template_key, [template_key])

        for source_key, source_value in source_sections.items():
            if any(term in source_key for term in candidate_terms):
                if source_value.strip():
                    return source_value

        template_tokens = set(template_key.split())
        best_key = None
        best_score = 0
        for source_key in source_sections.keys():
            source_tokens = set(source_key.split())
            overlap = len(template_tokens & source_tokens)
            if overlap > best_score:
                best_score = overlap
                best_key = source_key

        if best_key and best_score > 0:
            matched = source_sections.get(best_key, "").strip()
            return matched or None

        return None

    def _map_lfa_to_template(self, source_markdown: str) -> str:
        """
        Map call-specific LFA markdown onto the global template markdown structure.
        Falls back to source markdown if template is unavailable.
        """
        mapped_markdown, _ = self._map_lfa_to_template_with_report(source_markdown)
        return mapped_markdown

    def _map_lfa_to_template_with_report(self, source_markdown: str) -> tuple[str, Dict[str, Any]]:
        """
        Map call-specific LFA markdown onto the global template and return
        a structured mapping report for traceability.
        """
        if not self.lfa_template_markdown.exists():
            self.logger.warning(
                f"Global LFA template markdown not found: {self.lfa_template_markdown}. "
                "Using source markdown without template mapping."
            )
            return source_markdown, {
                "mapping_applied": False,
                "template_path": str(self.lfa_template_markdown),
                "template_sections_count": 0,
                "matched_count": 0,
                "unmatched_count": 0,
                "matched_template_sections": [],
                "unmatched_template_sections": [],
                "source_sections_found": sorted(list(self._extract_sections(source_markdown).keys()))
            }

        template_content = self.lfa_template_markdown.read_text(encoding="utf-8")
        source_sections = self._extract_sections(source_markdown)

        output_lines: List[str] = []
        current_template_key = None
        capture_buffer: List[str] = []
        template_section_keys: List[str] = []
        matched_template_sections: List[str] = []
        unmatched_template_sections: List[str] = []

        def flush_template_section():
            if current_template_key is None:
                return

            mapped_content = self._resolve_template_match(current_template_key, source_sections)
            if mapped_content:
                output_lines.extend(["", mapped_content.strip(), ""])
                matched_template_sections.append(current_template_key)
            else:
                # Do not leak generic template body text into call-specific outputs.
                output_lines.extend(["", "_No call-specific content provided for this section yet._", ""])
                unmatched_template_sections.append(current_template_key)

        for line in template_content.splitlines():
            if line.startswith("#"):
                flush_template_section()
                output_lines.append(line)
                current_template_key = self._normalize_heading(line.lstrip("#").strip())
                template_section_keys.append(current_template_key)
                capture_buffer = []
            else:
                capture_buffer.append(line)

        flush_template_section()
        mapped_markdown = "\n".join(output_lines).strip() + "\n"
        report = {
            "mapping_applied": True,
            "template_path": str(self.lfa_template_markdown),
            "template_sections_count": len(template_section_keys),
            "matched_count": len(matched_template_sections),
            "unmatched_count": len(unmatched_template_sections),
            "matched_template_sections": matched_template_sections,
            "unmatched_template_sections": unmatched_template_sections,
            "source_sections_found": sorted(list(source_sections.keys()))
        }
        return mapped_markdown, report

    def _normalize_block_for_dedup(self, text: str) -> str:
        """Normalize markdown blocks for lightweight redundancy removal."""
        lowered = text.lower()
        lowered = re.sub(r"#+\s*", "", lowered)
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _compile_call_context(self, call_files: List[Path]) -> tuple[Path, Dict[str, Any]]:
        """
        Combine all processed call documents into one deduplicated markdown file.
        Redundancy stripping is deterministic and paragraph-based.
        """
        context_dir = self.output_dir / "phase_a" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        compiled_path = context_dir / f"call_context_compiled_{self.session_id}.md"

        seen_blocks = set()
        kept_blocks = 0
        skipped_blocks = 0
        source_count = 0
        lines: List[str] = []

        lines.append("# Compiled Call Context")
        lines.append("")
        lines.append(f"_Generated by Phase A session {self.session_id}_")
        lines.append("")
        lines.append("## Source Documents")
        for file_path in call_files:
            lines.append(f"- {file_path.name}")
        lines.append("")
        lines.append("## Combined Context")
        lines.append("")

        for file_path in call_files:
            source_count += 1
            lines.append(f"### Source: {file_path.name}")
            lines.append("")
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]

            for block in blocks:
                normalized = self._normalize_block_for_dedup(block)
                if not normalized:
                    continue
                if normalized in seen_blocks:
                    skipped_blocks += 1
                    continue
                seen_blocks.add(normalized)
                lines.append(block)
                lines.append("")
                kept_blocks += 1

        compiled_content = "\n".join(lines).strip() + "\n"
        compiled_path.write_text(compiled_content, encoding="utf-8")

        stats = {
            "compiled_path": str(compiled_path),
            "source_documents": source_count,
            "unique_blocks_kept": kept_blocks,
            "redundant_blocks_removed": skipped_blocks,
            "compiled_chars": len(compiled_content),
        }
        return compiled_path, stats
    
    # -------------------------------------------------------------------------
    # VERSION CONTROL HELPERS
    # -------------------------------------------------------------------------
    # Creates timestamped markdown files for version control
    # Extracts version information from file paths
    # Ensures unique versioning for each processing run
    # -------------------------------------------------------------------------
    
    def _create_versioned_markdown(self, original_path: Path, markdown_content: str) -> Path:
        """
        Create a versioned markdown file with smart versioning logic.
        
        If the original Word document content is identical to a previously processed version,
        update the version number of the existing file instead of creating a new one.
        
        Args:
            original_path: Original file path
            markdown_content: Markdown content to save
            
        Returns:
            Path to the versioned markdown file
        """
        # Calculate hash of the original Word document
        original_hash = self._calculate_file_hash(original_path)
        
        # Check if we have an existing processed file with the same content
        existing_file = self._find_existing_version(original_path, original_hash)
        
        # Add hash metadata to markdown content for tracking
        enhanced_markdown_content = self._add_hash_metadata(markdown_content, original_path, original_hash)
        
        if existing_file:
            # Content is identical - update the version number of existing file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_versioned_filename = f"{original_path.stem}_processed_{timestamp}.md"
            new_versioned_path = original_path.parent / new_versioned_filename
            
            # Write the enhanced content to the new versioned file
            with open(new_versioned_path, 'w', encoding='utf-8') as f:
                f.write(enhanced_markdown_content)
            
            # Remove the old versioned file
            existing_file.unlink()
            
            self.logger.info(f"Content identical to existing version - updated version number")
            self.logger.info(f"Removed old version: {existing_file.name}")
            self.logger.info(f"Created new version: {new_versioned_path.name}")
            return new_versioned_path
        else:
            # Content is different - create a new versioned file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            versioned_filename = f"{original_path.stem}_processed_{timestamp}.md"
            versioned_path = original_path.parent / versioned_filename
            
            # Write enhanced markdown content
            with open(versioned_path, 'w', encoding='utf-8') as f:
                f.write(enhanced_markdown_content)
            
            self.logger.info(f"Content changed - created new versioned file: {versioned_path.name}")
            return versioned_path
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file for content comparison.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA256 hash as hexadecimal string
        """
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _add_hash_metadata(self, markdown_content: str, original_path: Path, content_hash: str) -> str:
        """
        Add hash metadata to markdown content for content tracking.
        
        Args:
            markdown_content: Original markdown content
            original_path: Path to the original file
            content_hash: SHA256 hash of the original file
            
        Returns:
            Enhanced markdown content with metadata
        """
        # Create metadata header
        metadata_header = f"""<!-- 
Document Processing Metadata
===========================
Original file: {original_path.name}
Original file hash: {content_hash}
Processed at: {datetime.now().isoformat()}
Session ID: {self.session_id}
Framework version: 1.0.0
-->

"""
        
        return metadata_header + markdown_content
    
    def _find_existing_version(self, original_path: Path, content_hash: str) -> Optional[Path]:
        """
        Find an existing processed markdown file with the same content hash.
        
        Args:
            original_path: Original file path
            content_hash: SHA256 hash of the original file content
            
        Returns:
            Path to existing file with same content, or None if not found
        """
        # Look for existing processed files for this document
        pattern = f"{original_path.stem}_processed_*.md"
        existing_files = list(original_path.parent.glob(pattern))
        
        for existing_file in existing_files:
            try:
                # Read the existing markdown file and check if it has metadata about the original hash
                with open(existing_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for hash metadata in the markdown file
                if f"Original file hash: {content_hash}" in content:
                    self.logger.info(f"Found existing version with identical content: {existing_file.name}")
                    return existing_file
                    
            except Exception as e:
                self.logger.warning(f"Could not read existing file {existing_file.name}: {e}")
                continue
        
        return None
    
    def _extract_version_from_path(self, file_path: Path) -> str:
        """
        Extract version information from the file path.
        
        Args:
            file_path: Path to the versioned file
            
        Returns:
            Version string
        """
        # Extract timestamp from filename (format: name_processed_YYYYMMDD_HHMMSS.md)
        filename = file_path.stem
        if '_processed_' in filename:
            version_part = filename.split('_processed_')[-1]
            return version_part
        return "unknown"
    
    # -------------------------------------------------------------------------
    # SNAPSHOT CREATION
    # -------------------------------------------------------------------------
    # Creates version control snapshots for complete traceability
    # Includes inputs, configuration, and outputs
    # Enables reproducibility and audit trail
    # -------------------------------------------------------------------------
    
    def create_processing_snapshot(self, processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a version control snapshot of the LFA processing.
        
        Args:
            processing_results: Results from LFA document processing
            
        Returns:
            Snapshot metadata
        """
        # Prepare inputs for snapshot
        inputs = {}
        for doc_name, doc_data in processing_results["processed_documents"].items():
            inputs[doc_name] = {
                "success": True,
                "file_path": doc_data["original_path"],
                "file_hash": doc_data["file_hash"],
                "file_size": doc_data["file_size"],
                "document_type": doc_data["document_type"],
                "processed_at": doc_data["processed_at"],
                "markdown": "",  # Don't store full content in snapshot
                "structured_content": {
                    "word_count": doc_data["word_count"],
                    "sections": [{"title": f"Section {i+1}"} for i in range(doc_data["sections"])]
                }
            }
        
        # Prepare configuration
        config = {
            "phase": "phase_a_lfa_processing",
            "session_id": self.session_id,
            "framework_root": str(self.framework_root),
            "call_dir": str(self.call_dir),
            "output_dir": str(self.output_dir),
            "processing_timestamp": datetime.now().isoformat()
        }
        
        # Prepare outputs
        outputs = {
            "processed_documents": processing_results["processed_documents"],
            "summary": processing_results["summary"],
            "errors": processing_results["errors"]
        }
        
        # Create snapshot
        snapshot = self.version_control.create_snapshot(
            session_id=self.session_id,
            phase="phase_a_lfa_processing",
            inputs=inputs,
            config=config,
            outputs=outputs
        )
        
        self.logger.info(f"Created processing snapshot: {snapshot['id']}")
        return snapshot
    
    # -------------------------------------------------------------------------
    # REPORTING AND OUTPUT
    # -------------------------------------------------------------------------
    # Creates comprehensive processing reports
    # Includes metadata, results, and next steps
    # Provides complete documentation of processing activities
    # -------------------------------------------------------------------------
    
    def save_processing_report(self, results: Dict[str, Any], snapshot: Dict[str, Any]) -> Path:
        """
        Save a comprehensive processing report.
        
        Args:
            results: Processing results dictionary
            snapshot: Snapshot metadata
            
        Returns:
            Path to the saved report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / "phase_a" / "processing_logs" / f"lfa_processing_log_{timestamp}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create comprehensive report
        report_data = {
            "metadata": {
                "session_id": self.session_id,
                "phase": "phase_a_lfa_processing",
                "framework_root": str(self.framework_root),
                "call_dir": str(self.call_dir),
                "output_dir": str(self.output_dir),
                "processed_at": datetime.now().isoformat(),
                "processor_version": "1.0.0"
            },
            "snapshot": snapshot,
            "processing_results": results,
            "next_steps": {
                "description": "LFA documents have been processed and versioned",
                "available_documents": list(results["processed_documents"].keys()),
                "recommended_action": "Proceed to LFA analysis using the versioned markdown files"
            }
        }
        
        import json
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Processing report saved: {report_path}")
        return report_path
    
    # -------------------------------------------------------------------------
    # MAIN PROCESSING WORKFLOW
    # -------------------------------------------------------------------------
    # Orchestrates the complete LFA document processing workflow
    # Coordinates discovery, processing, versioning, and reporting
    # Provides comprehensive error handling and logging
    # -------------------------------------------------------------------------
    
    def _run_lfa_restructuring(self, processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run LFA restructuring on processed documents.
        
        Produces lfa_structured.md and lfa_derivation.md in the phase_a output dir.
        Uses pre-phase context (summary.md, instructions.md) if available.
        """
        restructure_output = self.output_dir / "phase_a" / "lfa_restructured"
        restructure_output.mkdir(parents=True, exist_ok=True)
        
        all_results = {}
        
        # Find pre-phase context files
        context_dir = self.output_dir / "pre_phase" / "context"
        call_context_path = None
        instructions_path = None
        
        if context_dir.exists():
            # Find the most recent summary/context file
            for pattern in ["summary.md", "skill_test_sonnet.md", "call_context_compiled_*.md"]:
                candidates = sorted(context_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    call_context_path = candidates[0]
                    break
            
            instructions_candidates = sorted(context_dir.glob("instructions.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if instructions_candidates:
                instructions_path = instructions_candidates[0]
        
        if call_context_path:
            self.logger.info(f"Using call context: {call_context_path.name}")
        else:
            self.logger.info("No pre-phase call context found (run pre-phase first for better results)")
        
        if instructions_path:
            self.logger.info(f"Using instructions: {instructions_path.name}")
        
        template_path = self.lfa_template_markdown
        
        # Get synthesis model from call config (default to Sonnet)
        synthesis_model = self.call_config.get("synthesis_model", "claude-sonnet-4-20250514")
        
        for doc_name, doc_data in processing_results.get("processed_documents", {}).items():
            # Use saved raw markdown (before template mapping)
            raw_path = doc_data.get("raw_markdown_path")
            if raw_path and Path(raw_path).exists():
                raw_markdown = Path(raw_path).read_text(encoding="utf-8", errors="ignore")
            else:
                # Fallback to processed file
                self.logger.warning(f"Raw markdown not found for {doc_name}, using processed file")
                markdown_path = Path(doc_data["markdown_path"])
                raw_markdown = markdown_path.read_text(encoding="utf-8", errors="ignore")
            
            self.logger.info(f"Restructuring: {doc_name} ({len(raw_markdown):,} chars)")
            
            result = restructure_lfa(
                source_markdown=raw_markdown,
                call_context_path=call_context_path,
                instructions_path=instructions_path,
                template_path=template_path,
                output_dir=restructure_output,
                model=synthesis_model,
            )
            
            if result.get("ok"):
                self.logger.info(
                    f"✓ Restructured {doc_name}: "
                    f"structured={result.get('structured_chars', 0):,} chars, "
                    f"derivation={result.get('derivation_chars', 0):,} chars, "
                    f"{result.get('total_tokens', 0):,} tokens"
                )
            else:
                self.logger.error(f"✗ Restructuring failed for {doc_name}: {result.get('error')}")
            
            all_results[doc_name] = result
        
        return all_results

    def run(self) -> bool:
        """
        Run the complete Phase A LFA processing and analysis workflow.
        
        This method orchestrates the entire Phase A workflow:
        1. SECTION 1: LFA Document Processing
           - Discovers LFA documents from input directory
           - Processes Word documents to markdown with version control
           - Creates comprehensive snapshots for audit trail
           
        2. SECTION 2: LFA Analysis and Review
           - Discovers latest processed files for review
           - Runs comprehensive LFA evaluation using new structured engine
           - Generates detailed reports with scores, evidence, gaps, and fixes
           - Creates review snapshots for traceability
        
        The workflow provides:
        - Complete traceability through version control and snapshots
        - Comprehensive error handling and logging
        - Integration with the new structured review engine
        - Detailed reporting and audit trails
        
        Returns:
            bool: True if processing was successful, False otherwise
            
        Note:
            The workflow automatically proceeds from Section 1 to Section 2
            if LFA documents are successfully processed. Section 2 uses the
            new structured review engine directly.
        """
        try:
            overall_start = time.time()
            self.logger.info("Starting Phase A LFA document processing...")
            
            # Discover LFA documents
            step_start = time.time()
            lfa_documents = self.discover_lfa_documents()
            discovery_time = time.time() - step_start
            print(f"⏱️  LFA discovery completed in {discovery_time:.2f}s")
            self.logger.info(f"⏱️  LFA discovery completed in {discovery_time:.2f}s")
            
            if not lfa_documents:
                self.logger.warning("No LFA documents found to process")
                return True
            
            # Process LFA documents
            step_start = time.time()
            results = self.process_lfa_documents(lfa_documents)
            processing_time = time.time() - step_start
            print(f"⏱️  LFA processing completed in {processing_time:.2f}s")
            self.logger.info(f"⏱️  LFA processing completed in {processing_time:.2f}s")
            
            # Create version control snapshot
            step_start = time.time()
            snapshot = self.create_processing_snapshot(results)
            snapshot_time = time.time() - step_start
            print(f"⏱️  Snapshot creation completed in {snapshot_time:.2f}s")
            self.logger.info(f"⏱️  Snapshot creation completed in {snapshot_time:.2f}s")
            
            # Save processing report
            step_start = time.time()
            report_path = self.save_processing_report(results, snapshot)
            report_time = time.time() - step_start
            print(f"⏱️  Report generation completed in {report_time:.2f}s")
            self.logger.info(f"⏱️  Report generation completed in {report_time:.2f}s")
            
            # Log final status
            if results["success"]:
                self.logger.info("✓ Phase A Section 1 (LFA Processing) completed successfully")
                self.logger.info(f"Session ID: {self.session_id}")
                self.logger.info(f"Snapshot: {snapshot['id']}")
                self.logger.info(f"Report: {report_path}")
                
                # List processed documents
                self.logger.info("Processed LFA documents:")
                for doc_name, doc_data in results["processed_documents"].items():
                    self.logger.info(f"  - {doc_name}: {doc_data['version']}")
                
                # Proceed to Section 2: LFA Analysis and Review
                # This section uses the new structured review engine directly
                section1_time = time.time() - overall_start
                print(f"⏱️  SECTION 1 TOTAL TIME: {section1_time:.2f}s")
                self.logger.info(f"⏱️  SECTION 1 TOTAL TIME: {section1_time:.2f}s")
                self.logger.info("")
                self.logger.info("=" * 60)
                self.logger.info("SECTION 1.5: LFA RESTRUCTURING")
                self.logger.info("=" * 60)
                
                # Restructure the processed LFA into structured + derivation files
                step_start = time.time()
                restructure_results = self._run_lfa_restructuring(results)
                restructure_time = time.time() - step_start
                print(f"⏱️  LFA restructuring completed in {restructure_time:.2f}s")
                self.logger.info(f"⏱️  LFA restructuring completed in {restructure_time:.2f}s")
                
                self.logger.info("")
                self.logger.info("=" * 60)
                self.logger.info("SECTION 2A: STRUCTURAL REVIEW")
                self.logger.info("=" * 60)
                self.logger.info("Evaluating LFA structural quality against LFA methodology")
                
                # Initialize analysis processor
                step_start = time.time()
                analysis_processor = LFAAnalysisProcessor(
                    framework_root=self.framework_root,
                    call_dir=self.call_dir,
                    call_config=self.call_config,
                    output_dir=self.output_dir,
                    session_id=self.session_id
                )
                init_time = time.time() - step_start
                self.logger.info(f"⏱️  Analysis processor initialized in {init_time:.2f}s")
                
                # Discover review inputs
                step_start = time.time()
                review_inputs = analysis_processor.discover_review_inputs()
                input_discovery_time = time.time() - step_start
                print(f"⏱️  Review input discovery completed in {input_discovery_time:.2f}s")
                self.logger.info(f"⏱️  Review input discovery completed in {input_discovery_time:.2f}s")
                
                if not review_inputs:
                    self.logger.warning("No review inputs found, skipping Section 2")
                    return results["success"]
                
                # Section 2A: Structural Review (LC + CQ)
                step_start = time.time()
                structural_results = analysis_processor.run_structural_review(review_inputs)
                structural_time = time.time() - step_start
                print(f"⏱️  Structural review completed in {structural_time:.2f}s")
                self.logger.info(f"⏱️  Structural review completed in {structural_time:.2f}s")
                
                # Section 2B: Call Alignment Review (CA)
                self.logger.info("")
                self.logger.info("=" * 60)
                self.logger.info("SECTION 2B: CALL ALIGNMENT REVIEW")
                self.logger.info("=" * 60)
                self.logger.info("Evaluating LFA alignment with call requirements")
                
                step_start = time.time()
                alignment_results = analysis_processor.run_alignment_review(review_inputs)
                alignment_time = time.time() - step_start
                print(f"⏱️  Alignment review completed in {alignment_time:.2f}s")
                self.logger.info(f"⏱️  Alignment review completed in {alignment_time:.2f}s")
                
                review_results = {
                    "success": structural_results.get("success", False) or alignment_results.get("success", False),
                    "structural": structural_results,
                    "alignment": alignment_results,
                    "inputs_used": {k: str(v) for k, v in review_inputs.items()},
                    "session_id": self.session_id,
                    "review_timestamp": datetime.now().isoformat(),
                }
                
                if review_results["success"]:
                    # Create review snapshot
                    step_start = time.time()
                    review_snapshot = analysis_processor.create_review_snapshot(review_results)
                    snapshot_time = time.time() - step_start
                    print(f"⏱️  Review snapshot creation completed in {snapshot_time:.2f}s")
                    self.logger.info(f"⏱️  Review snapshot creation completed in {snapshot_time:.2f}s")
                    
                    # Calculate total times
                    section2_time = time.time() - overall_start - section1_time
                    total_time = time.time() - overall_start
                    
                    self.logger.info("✓ Phase A Section 2 (LFA Analysis) completed successfully")
                    print(f"⏱️  SECTION 2 TOTAL TIME: {section2_time:.2f}s")
                    print(f"⏱️  PHASE A TOTAL TIME: {total_time:.2f}s")
                    self.logger.info(f"⏱️  SECTION 2 TOTAL TIME: {section2_time:.2f}s")
                    self.logger.info(f"⏱️  PHASE A TOTAL TIME: {total_time:.2f}s")
                    self.logger.info(f"Review Snapshot: {review_snapshot['id']}")
                    if structural_results.get("review_output_path"):
                        self.logger.info(f"Structural Review: {structural_results['review_output_path']}")
                    if alignment_results.get("review_output_path"):
                        self.logger.info(f"Alignment Review: {alignment_results['review_output_path']}")
                else:
                    self.logger.error("✗ Phase A Section 2 (LFA Analysis) failed")
                    self.logger.error(f"Error: {review_results.get('error', 'Unknown error')}")
                
            else:
                self.logger.error("✗ Phase A Section 1 (LFA Processing) completed with errors")
                self.logger.error(f"Errors: {results['errors']}")
            
            return results["success"]
            
        except Exception as e:
            self.logger.error(f"Fatal error in Phase A processing: {str(e)}")
            return False


# =============================================================================
# SECTION 2: LFA ANALYSIS AND REVIEW
# =============================================================================
# This section performs LFA content analysis and review using the NEW STRUCTURED
# review engine. It automatically discovers the latest processed LFA documents
# and static files from pre-phase, then runs comprehensive analysis.
# 
# NEW ENGINE FEATURES:
# - Structured evaluation with CA/LC/CQ criteria (Call Alignment, Logic Consistency, Content Quality)
# - Hybrid approach: LLM reasoning + Python deterministic checks
# - Evidence-based assessment with specific quotes and locations
# - Actionable gaps identification and specific fixes
# - Quantitative scoring (0-5 scale) with weighted totals
# - Comprehensive reporting (JSON + Markdown)
# 
# Key Components:
# - Automatic file discovery for review inputs
# - Direct integration with new structured review engine
# - LFA content analysis and call alignment assessment
# - Quality scoring and recommendations
# - Report generation and output integration
# =============================================================================

class LFAAnalysisProcessor:
    """
    Handles LFA analysis and review using the new structured review engine.
    
    This class integrates with the new structured review engine to provide comprehensive
    LFA evaluation. It replaces the old single-LLM-call approach with a sophisticated
    hybrid evaluation system that combines LLM reasoning with deterministic Python checks.
    
    The new review engine provides:
    - Call Alignment (CA): 30% weight - objectives, scope, outcomes, evaluation coverage
    - Logic Consistency (LC): 50% weight - hierarchy, traceability, KPIs, risks  
    - Content Quality (CQ): 20% weight - specificity, writing quality, terminology
    
    Key Features:
    - Structured evaluation with specific rubrics for each criterion
    - Evidence-based assessment with quotes and locations
    - Actionable gaps identification and specific fixes
    - Quantitative scoring (0-5 scale) with weighted totals
    - Hybrid approach: LLM reasoning + Python deterministic checks
    - Comprehensive reporting (JSON + Markdown)
    
    The integration directly uses the new structured review engine,
    providing significantly enhanced evaluation capabilities.
    
    Attributes:
        framework_root (Path): Root directory of the project framework
        output_dir (Path): Output directory for review reports
        session_id (str): Current session ID for traceability
        logger (Logger): Configured logger for this session
    """
    
    def __init__(
        self,
        framework_root: Path,
        call_dir: Path,
        call_config: Dict[str, Any],
        output_dir: Path,
        session_id: str,
    ):
        """
        Initialize the LFA analysis processor.
        
        Args:
            framework_root: Root directory of the project framework
            call_dir: Call-specific workspace directory
            call_config: Parsed call.yaml configuration
            output_dir: Output directory for reports
            session_id: Current session ID for traceability
        """
        self.framework_root = framework_root
        self.call_dir = call_dir
        self.call_config = call_config
        self.output_dir = output_dir
        self.session_id = session_id
        self.logger = logging.getLogger(f"phase_a.{session_id}")
    
    def _load_llm_config(self) -> Dict[str, Any]:
        """Load LLM configuration from simplified project config file."""
        config_path = self.call_dir / "call.yaml"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            # Simple config structure - review_model for evaluations, model for extraction
            return {
                "model": config.get("review_model", config.get("synthesis_model", "claude-sonnet-4-20250514")),
                "project_name": config.get("project_name", "Project"),
                "funding_type": config.get("funding_type", "generic"),
                "temperature": 0.0,  # Hardcoded for consistency
                "preferred_provider": "openai",
                "timeout_seconds": 180  # Hardcoded default
            }
        except (FileNotFoundError, yaml.YAMLError) as e:
            self.logger.warning(f"Could not load config from {config_path}: {e}")
            self.logger.warning("Using default configuration")
            return {
                "model": "claude-sonnet-4-20250514",
                "project_name": "Project",
                "funding_type": "generic",
                "temperature": 0.0,
                "preferred_provider": "openai",
                "timeout_seconds": 180
            }

    def _normalize_block_for_dedup(self, text: str) -> str:
        """Normalize markdown blocks for lightweight redundancy removal."""
        lowered = text.lower()
        lowered = re.sub(r"#+\s*", "", lowered)
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _compile_call_context(self, call_files: List[Path]) -> tuple[Path, Dict[str, Any]]:
        """
        Combine all processed call documents into one deduplicated markdown file.
        Redundancy stripping is deterministic and paragraph-based.
        """
        context_dir = self.output_dir / "phase_a" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        compiled_path = context_dir / f"call_context_compiled_{self.session_id}.md"

        seen_blocks = set()
        kept_blocks = 0
        skipped_blocks = 0
        source_count = 0
        lines: List[str] = []

        lines.append("# Compiled Call Context")
        lines.append("")
        lines.append(f"_Generated by Phase A session {self.session_id}_")
        lines.append("")
        lines.append("## Source Documents")
        for file_path in call_files:
            lines.append(f"- {file_path.name}")
        lines.append("")
        lines.append("## Combined Context")
        lines.append("")

        for file_path in call_files:
            source_count += 1
            lines.append(f"### Source: {file_path.name}")
            lines.append("")
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]

            for block in blocks:
                normalized = self._normalize_block_for_dedup(block)
                if not normalized:
                    continue
                if normalized in seen_blocks:
                    skipped_blocks += 1
                    continue
                seen_blocks.add(normalized)
                lines.append(block)
                lines.append("")
                kept_blocks += 1

        compiled_content = "\n".join(lines).strip() + "\n"
        compiled_path.write_text(compiled_content, encoding="utf-8")

        stats = {
            "compiled_path": str(compiled_path),
            "source_documents": source_count,
            "unique_blocks_kept": kept_blocks,
            "redundant_blocks_removed": skipped_blocks,
            "compiled_chars": len(compiled_content),
        }
        return compiled_path, stats
    
    def discover_review_inputs(self) -> Dict[str, Path]:
        """
        Discover the latest processed files for review.
        
        This method automatically discovers the required input files for LFA review:
        1. Latest processed LFA document from input/lfa_documents/
        2. Call document from pre-phase processing in input/call_documents/
        3. Review criteria from config/review_criteria_scoring/
        
        The discovery process:
        - Finds the most recent LFA document (by modification time)
        - Locates the call document from pre-phase processing
        - Identifies the review criteria configuration
        - Validates that all required inputs are available
        
        Returns:
            Dict[str, Path]: Dictionary containing:
                - 'lfa_document': Path to latest processed LFA document
                - 'call_document': Path to call document from pre-phase
                - 'criteria': Path to review criteria configuration
                
        Note:
            Only the latest LFA document is used for review to ensure
            the most current version is evaluated.
        """
        inputs = {}
        
        # Find latest LFA document — prefer restructured version if available
        restructured_lfa = self.output_dir / "phase_a" / "lfa_restructured" / "lfa_structured.md"
        if restructured_lfa.exists():
            inputs["lfa_document"] = restructured_lfa
            self.logger.info(f"Using restructured LFA: {restructured_lfa.name}")
        else:
            lfa_docs_dir = self.call_dir / "input" / "lfa_documents"
            if lfa_docs_dir.exists():
                lfa_files = [f for f in lfa_docs_dir.glob("*_processed_*.md")]
                if lfa_files:
                    latest_lfa = max(lfa_files, key=lambda f: f.stat().st_mtime)
                    inputs["lfa_document"] = latest_lfa
                    self.logger.info(f"Found latest LFA document: {latest_lfa.name}")
        
        # Find call context — prefer pre-phase synthesized summary if available
        context_dir = self.output_dir / "pre_phase" / "context"
        pre_phase_summary = None
        if context_dir.exists():
            for pattern in ["summary.md", "skill_test_sonnet.md", "call_context_compiled_*.md"]:
                candidates = sorted(context_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    pre_phase_summary = candidates[0]
                    break
        
        if pre_phase_summary:
            inputs["call_document"] = pre_phase_summary
            self.logger.info(f"Using pre-phase synthesized context: {pre_phase_summary.name}")
        else:
            # Fallback: compile from processed call documents
            call_docs_dir = self.call_dir / "input" / "call_documents"
            if call_docs_dir.exists():
                call_files = sorted([f for f in call_docs_dir.glob("*_processed.md")], key=lambda p: p.name.lower())
                if call_files:
                    compiled_path, compile_stats = self._compile_call_context(call_files)
                    inputs["call_document"] = compiled_path
                    self.logger.info(
                        "Compiled call context from "
                        f"{compile_stats['source_documents']} files "
                        f"({compile_stats['unique_blocks_kept']} unique blocks, "
                        f"{compile_stats['redundant_blocks_removed']} redundant removed)"
                    )
                    self.logger.info(f"Compiled call context: {compiled_path.name}")
        
        # Find review criteria
        funding_type = self.call_config.get("funding_type", "generic")
        criteria_file = self.framework_root / "config" / "review_criteria_scoring" / f"{funding_type}_phase_a.md"
        if criteria_file.exists():
            inputs["criteria"] = criteria_file
            self.logger.info(f"Found review criteria: {criteria_file.name}")
        
        # Find LFA template for structural review
        template_path = self.framework_root / "templates" / "input_templates" / "lfa_template.md"
        if template_path.exists():
            inputs["lfa_template"] = template_path
            self.logger.info(f"Found LFA template: {template_path.name}")
        
        return inputs

    def _save_review_output(self, result: Dict[str, Any], prefix: str, subfolder: str = "") -> str:
        """Save review results as md, json, and docx. Returns md path."""
        review_results_dir = self.output_dir / "phase_a" / "review_results"
        if subfolder:
            review_results_dir = review_results_dir / subfolder
        review_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Save markdown report
        review_output_path = str(review_results_dir / f"{prefix}_{self.session_id}.md")
        if "report_md_path" in result:
            original = pathlib.Path(result["report_md_path"])
            if original.exists():
                target = review_results_dir / f"{prefix}_{self.session_id}.md"
                original.rename(target)
                review_output_path = str(target)
        
        # Save JSON
        json_path = review_results_dir / f"{prefix}_{self.session_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Generate Word doc
        try:
            from scripts.review_engine.word_export import export_review_to_word
            word_path = review_results_dir / f"{prefix}_{self.session_id}.docx"
            export_review_to_word(result, str(word_path))
            self.logger.info(f"Word report generated: {word_path}")
        except Exception as e:
            self.logger.warning(f"Failed to generate Word report: {e}")
        
        return review_output_path

    def run_structural_review(self, inputs: Dict[str, Path]) -> Dict[str, Any]:
        """Layer 1: Evaluate LFA structural quality (LC + CQ). No call document needed."""
        try:
            import sys
            sys.path.append(str(self.framework_root / "scripts" / "review_engine"))
            from review_engine import run_structural_review
            
            if "lfa_document" not in inputs:
                raise ValueError("Missing lfa_document input")
            
            self.logger.info("Starting structural review...")
            self.logger.info(f"LFA Document: {inputs['lfa_document'].name}")
            if "lfa_template" in inputs:
                self.logger.info(f"LFA Template: {inputs['lfa_template'].name}")
            
            llm_config = self._load_llm_config()
            
            result = run_structural_review(
                lfa_md_path=str(inputs["lfa_document"]),
                lfa_template_path=str(inputs.get("lfa_template", "")),
                run_config_path=str(self.framework_root / "scripts" / "review_engine" / "criteria.json"),
                model=llm_config["model"],
                temperature=llm_config["temperature"],
                project_name=llm_config["project_name"],
                prompts_dir=str(self.framework_root / "scripts" / "review_engine" / "prompts"),
                return_markdown_report=True,
                max_chars_lfa=30000,
            )
            
            review_path = self._save_review_output(result, "structural_review", subfolder="structural")
            
            self.logger.info(f"✓ Structural review completed: {review_path}")
            return {
                "success": True,
                "review_output_path": review_path,
                "scores": result.get("scores", {}),
                "session_id": self.session_id,
            }
            
        except Exception as e:
            self.logger.error(f"✗ Structural review failed: {e}")
            return {"success": False, "error": str(e), "session_id": self.session_id}

    def run_alignment_review(self, inputs: Dict[str, Path]) -> Dict[str, Any]:
        """Layer 2: Evaluate LFA alignment with call requirements (CA only)."""
        try:
            import sys
            sys.path.append(str(self.framework_root / "scripts" / "review_engine"))
            from review_engine import run_alignment_review
            
            if "lfa_document" not in inputs or "call_document" not in inputs:
                raise ValueError("Missing lfa_document or call_document input")
            
            self.logger.info("Starting call alignment review...")
            self.logger.info(f"LFA Document: {inputs['lfa_document'].name}")
            self.logger.info(f"Call Document: {inputs['call_document'].name}")
            
            llm_config = self._load_llm_config()
            
            result = run_alignment_review(
                lfa_md_path=str(inputs["lfa_document"]),
                call_md_path=str(inputs["call_document"]),
                run_config_path=str(self.framework_root / "scripts" / "review_engine" / "criteria.json"),
                model=llm_config["model"],
                temperature=llm_config["temperature"],
                project_name=llm_config["project_name"],
                prompts_dir=str(self.framework_root / "scripts" / "review_engine" / "prompts"),
                eligibility_checklist_path=str(self.framework_root / "scripts" / "review_engine" / "eligibility_checklist.json"),
                return_markdown_report=True,
                max_chars_call=50000,
                max_chars_lfa=30000,
            )
            
            review_path = self._save_review_output(result, "alignment_review", subfolder="alignment")
            
            self.logger.info(f"✓ Alignment review completed: {review_path}")
            return {
                "success": True,
                "review_output_path": review_path,
                "scores": result.get("scores", {}),
                "session_id": self.session_id,
            }
            
        except Exception as e:
            self.logger.error(f"✗ Alignment review failed: {e}")
            return {"success": False, "error": str(e), "session_id": self.session_id}

    def run_lfa_review(self, inputs: Dict[str, Path]) -> Dict[str, Any]:
        """
        Run LFA review using the new structured review engine.
        
        This method orchestrates the comprehensive LFA evaluation using the new
        structured review engine. It replaces the old single-LLM-call approach
        with a sophisticated hybrid evaluation system.
        
        The review process:
        1. Validates required input files are available
        2. Imports the new review engine directly
        3. Executes structured evaluation with CA/LC/CQ criteria
        4. Generates comprehensive reports (JSON + Markdown)
        5. Handles errors gracefully with detailed logging
        
        The new engine provides:
        - Call Alignment (CA): 30% weight - objectives, scope, outcomes, evaluation coverage
        - Logic Consistency (LC): 50% weight - hierarchy, traceability, KPIs, risks
        - Content Quality (CQ): 20% weight - specificity, writing quality, terminology
        
        Each criterion is evaluated with:
        - Evidence-based assessment with specific quotes and locations
        - Actionable gaps identification
        - Specific, imperative fixes
        - Quantitative scoring (0-5 scale)
        
        Args:
            inputs (Dict[str, Path]): Dictionary containing:
                - 'lfa_document': Path to LFA document
                - 'call_document': Path to call document  
                - 'criteria': Path to review criteria
                
        Returns:
            Dict[str, Any]: Review results containing:
                - success (bool): Review execution success status
                - review_output_path (str): Path to generated review report
                - inputs_used (dict): Input files used for review
                - session_id (str): Session identifier
                - review_timestamp (str): ISO timestamp of review execution
                
        Note:
            This method directly integrates with the new structured review engine,
            providing significantly enhanced evaluation capabilities with CA/LC/CQ criteria.
        """
        try:
            # Import new structured review engine directly
            import sys
            sys.path.append(str(self.framework_root / "scripts" / "review_engine"))
            from review_engine import run_review
            
            # Validate required inputs
            required_inputs = ["lfa_document", "call_document", "criteria"]
            missing_inputs = [inp for inp in required_inputs if inp not in inputs]
            
            if missing_inputs:
                raise ValueError(f"Missing required inputs: {missing_inputs}")
            
            self.logger.info("Starting LFA review analysis...")
            self.logger.info(f"LFA Document: {inputs['lfa_document'].name}")
            self.logger.info(f"Call Document: {inputs['call_document'].name}")
            self.logger.info(f"Criteria: {inputs['criteria'].name}")
            
            # Load LLM configuration from project config
            llm_config = self._load_llm_config()
            
            # Run review using new structured engine directly
            # This provides enhanced evaluation with CA/LC/CQ criteria
            result = run_review(
                lfa_md_path=str(inputs["lfa_document"]),
                call_md_path=str(inputs["call_document"]),
                run_config_path=str(self.framework_root / "scripts" / "review_engine" / "criteria.json"),
                model=llm_config["model"],
                temperature=llm_config["temperature"],
                project_name=llm_config["project_name"],
                prompts_dir=str(self.framework_root / "scripts" / "review_engine" / "prompts"),
                eligibility_checklist_path=str(self.framework_root / "scripts" / "review_engine" / "eligibility_checklist.json"),
                return_markdown_report=True,
                max_chars_call=50000,
                max_chars_lfa=30000,
                test_mode=False  # Use actual LLM for real analysis
            )
            
            # Move the generated report to the expected location
            review_results_dir = self.output_dir / "phase_a" / "review_results"
            review_results_dir.mkdir(parents=True, exist_ok=True)
            if "report_md_path" in result:
                original_report = pathlib.Path(result["report_md_path"])
                if original_report.exists():
                    expected_report_path = review_results_dir / f"lfa_review_result_{self.session_id}.md"
                    original_report.rename(expected_report_path)
                    review_output_path = str(expected_report_path)
                else:
                    review_output_path = str(review_results_dir / f"lfa_review_result_{self.session_id}_error.md")
            else:
                review_output_path = str(review_results_dir / f"lfa_review_result_{self.session_id}_error.md")
            
            # Save detailed JSON results
            json_report_path = review_results_dir / f"lfa_review_result_{self.session_id}.json"
            with open(json_report_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Generate Word document automatically
            try:
                from scripts.review_engine.word_export import export_review_to_word
                word_output_path = review_results_dir / f"lfa_review_result_{self.session_id}.docx"
                export_review_to_word(result, str(word_output_path))
                self.logger.info(f"Word report generated: {word_output_path}")
            except Exception as e:
                self.logger.warning(f"Failed to generate Word report: {e}")
            
            # Prepare results
            results = {
                "success": True,
                "review_output_path": review_output_path,
                "inputs_used": {k: str(v) for k, v in inputs.items()},
                "session_id": self.session_id,
                "review_timestamp": datetime.now().isoformat()
            }
            
            self.logger.info(f"✓ LFA review completed successfully")
            self.logger.info(f"Review result: {review_output_path}")
            
            return results
            
        except Exception as e:
            error_msg = f"LFA review failed: {str(e)}"
            self.logger.error(f"✗ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "session_id": self.session_id,
                "review_timestamp": datetime.now().isoformat()
            }
    
    def create_review_snapshot(self, review_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a version control snapshot of the LFA review.
        
        Args:
            review_results: Results from LFA review
            
        Returns:
            Snapshot metadata
        """
        # Initialize version control
        version_control = VersionControl(self.output_dir / "snapshots")
        
        # Prepare inputs for snapshot
        inputs = {}
        if review_results.get("success"):
            for input_type, input_path in review_results.get("inputs_used", {}).items():
                inputs[input_type] = {
                    "success": True,
                    "file_path": input_path,
                    "file_hash": "",  # Could be calculated if needed
                    "document_type": input_type,
                    "processed_at": review_results.get("review_timestamp")
                }
        
        # Prepare configuration
        config = {
            "phase": "phase_a_lfa_review",
            "session_id": self.session_id,
            "framework_root": str(self.framework_root),
            "call_dir": str(self.call_dir),
            "output_dir": str(self.output_dir),
            "review_timestamp": review_results.get("review_timestamp")
        }
        
        # Prepare outputs
        outputs = {
            "review_results": review_results,
            "review_output_path": review_results.get("review_output_path", "")
        }
        
        # Create snapshot
        snapshot = version_control.create_snapshot(
            session_id=self.session_id,
            phase="phase_a_lfa_review",
            inputs=inputs,
            config=config,
            outputs=outputs
        )
        
        self.logger.info(f"Created review snapshot: {snapshot['id']}")
        return snapshot


# =============================================================================
# SECTION 3: INTEGRATION (FUTURE IMPLEMENTATION)  
# =============================================================================
# This section will handle integration with other phases and will include:
# - Integration with other phases (B, C)
# - Output preparation for Phase B
# - Cross-phase data sharing
# - Final report assembly
# =============================================================================


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================
# Provides command-line access to Phase A functionality
# Handles argument parsing and processor initialization
# =============================================================================

def main(argv=None):
    """
    Main entry point for Phase A LFA processing and analysis.
    
    This function provides the command-line interface for the complete Phase A workflow,
    which includes both LFA document processing and comprehensive analysis using the
    new structured review engine.
    
    The workflow:
    1. Processes LFA documents from Word to markdown with version control
    2. Runs comprehensive LFA evaluation using CA/LC/CQ criteria
    3. Generates detailed reports with scores, evidence, gaps, and fixes
    4. Creates snapshots for complete traceability
    
    Command-line arguments:
        --framework-root: Root directory of the project framework
        --output-dir: Output directory for reports and snapshots
        --verbose: Enable verbose logging for debugging
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
        
    Note:
        Requires OpenAI API key (OPENAI_API_KEY environment variable) for
        the structured review engine evaluation.
    """
    parser = argparse.ArgumentParser(
        description="Phase A: LFA Document Processing and Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_phase_a.py --call my-call
  python3 run_phase_a.py --framework-root /path/to/project framework
  python3 run_phase_a.py --output-dir /path/to/output
  python3 run_phase_a.py --verbose
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
        help="Output directory for reports and snapshots (default: calls/<call>/output)"
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
        call_config = load_call_config(call_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    load_env_for_call(call_dir, args.framework_root)
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize and run processor
    processor = PhaseAProcessor(
        framework_root=args.framework_root,
        call_dir=call_dir,
        call_config=call_config,
        output_dir=args.output_dir
    )
    
    success = processor.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
