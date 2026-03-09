#!/usr/bin/env python3
"""
project framework - Document Processor

This module handles document ingestion, normalization, and content extraction
using MarkItDown and other processing tools.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import MarkItDown for document processing
try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    MarkItDown = None


class DocumentProcessor:
    """
    Handles document ingestion and normalization for the framework.
    
    Converts various document formats (DOCX, PDF, TXT, MD) into normalized
    Markdown and JSON formats for consistent processing.
    """
    
    def __init__(self, config: Dict[str, Any], reference_guides: Dict[str, str] = None):
        """
        Initialize the document processor.
        
        Args:
            config: Framework configuration dictionary
            reference_guides: Optional reference guides for best practices
        """
        self.config = config
        self.reference_guides = reference_guides or {}
        self.markitdown = MarkItDown() if MARKITDOWN_AVAILABLE else None
        
        if not MARKITDOWN_AVAILABLE:
            print("⚠️  Warning: MarkItDown not available. Install with: pip install 'markitdown[all]'")
        
        # Apply MarkItDown best practices if guide available
        if 'markitdown' in self.reference_guides:
            self._apply_markitdown_best_practices()
    
    def _apply_markitdown_best_practices(self):
        """Apply best practices from MarkItDown integration guide."""
        # Extract best practices from the guide
        # This could parse the guide and apply specific settings
        if self.markitdown:
            # Apply any specific MarkItDown configurations based on guide
            pass
    
    def process_document(self, file_path: Path, document_type: str) -> Dict[str, Any]:
        """
        Process a document and extract content in multiple formats.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document (e.g., "lfa_draft", "call_document", "wp_description")
            
        Returns:
            Dictionary containing processed content and metadata
        """
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "document_type": document_type,
                "file_path": str(file_path)
            }
        
        # Calculate file hash for version control
        file_hash = self._calculate_file_hash(file_path)
        
        # Process based on file extension
        file_extension = file_path.suffix.lower()
        
        try:
            if file_extension in ['.docx', '.doc']:
                result = self._process_word_document(file_path)
            elif file_extension == '.pdf':
                result = self._process_pdf_document(file_path, document_type)
            elif file_extension in ['.md', '.txt']:
                result = self._process_text_document(file_path)
            elif file_extension in ['.yaml', '.yml']:
                result = self._process_yaml_document(file_path)
            elif file_extension == '.json':
                result = self._process_json_document(file_path)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported file format: {file_extension}",
                    "document_type": document_type,
                    "file_path": str(file_path)
                }
            
            if result["success"]:
                # Extract structured content based on document type
                structured_content = self._extract_structured_content(
                    result["markdown"], document_type
                )
                
                # Add metadata
                result.update({
                    "document_type": document_type,
                    "file_path": str(file_path),
                    "file_hash": file_hash,
                    "file_size": file_path.stat().st_size,
                    "processed_at": datetime.now().isoformat(),
                    "structured_content": structured_content
                })
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Processing error: {str(e)}",
                "document_type": document_type,
                "file_path": str(file_path)
            }
    
    def _process_word_document(self, file_path: Path) -> Dict[str, Any]:
        """Process Word document using MarkItDown."""
        if not self.markitdown:
            return {
                "success": False,
                "error": "MarkItDown not available for Word document processing"
            }
        
        result = self.markitdown.convert(str(file_path))
        
        if result and result.text_content:
            return {
                "success": True,
                "markdown": result.text_content,
                "raw_content": result.text_content,
                "processing_method": "markitdown"
            }
        else:
            return {
                "success": False,
                "error": "Failed to extract content from Word document"
            }
    
    def _process_pdf_document(self, file_path: Path, document_type: str = None) -> Dict[str, Any]:
        """Process PDF document using MarkItDown."""
        if not self.markitdown:
            return {
                "success": False,
                "error": "MarkItDown not available for PDF document processing"
            }
        
        result = self.markitdown.convert(str(file_path))
        
        if result and result.text_content:
            markdown_content = result.text_content
            
            # If this is a call document, apply call extraction
            if document_type == "call_document":
                try:
                    from call_extractor import CallExtractor, load_project_config
                    
                    # Load project configuration
                    project_config = load_project_config()
                    extractor = CallExtractor(project_config)
                    
                    # Check if this document contains our target call
                    if extractor.should_extract_call(markdown_content):
                        # Extract the specific call content
                        extracted_content, extraction_metadata = extractor.extract_call_content(markdown_content)
                        
                        return {
                            "success": True,
                            "markdown": extracted_content,
                            "raw_content": result.text_content,
                            "processing_method": "markitdown_with_call_extraction",
                            "extraction_metadata": extraction_metadata,
                            "call_extracted": True
                        }
                    else:
                        print(f"⚠️  Warning: Target call not found in {file_path.name}")
                        return {
                            "success": True,
                            "markdown": markdown_content,
                            "raw_content": result.text_content,
                            "processing_method": "markitdown",
                            "call_extracted": False,
                            "warning": "Target call not found in document"
                        }
                        
                except ImportError:
                    print("⚠️  Warning: Call extractor not available, processing full document")
                    return {
                        "success": True,
                        "markdown": markdown_content,
                        "raw_content": result.text_content,
                        "processing_method": "markitdown",
                        "call_extracted": False
                    }
                except Exception as e:
                    print(f"⚠️  Warning: Call extraction failed: {e}, processing full document")
                    return {
                        "success": True,
                        "markdown": markdown_content,
                        "raw_content": result.text_content,
                        "processing_method": "markitdown",
                        "call_extracted": False,
                        "extraction_error": str(e)
                    }
            
            # For non-call documents, return as-is
            return {
                "success": True,
                "markdown": markdown_content,
                "raw_content": result.text_content,
                "processing_method": "markitdown"
            }
        else:
            return {
                "success": False,
                "error": "Failed to extract content from PDF document"
            }
    
    def _process_text_document(self, file_path: Path) -> Dict[str, Any]:
        """Process text/markdown document."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "markdown": content,
                "raw_content": content,
                "processing_method": "direct_text"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read text file: {str(e)}"
            }
    
    def _process_yaml_document(self, file_path: Path) -> Dict[str, Any]:
        """Process YAML document."""
        try:
            import yaml
            
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml_content = yaml.safe_load(f)
                raw_content = f.read()
            
            # Convert YAML to markdown for display
            markdown_content = f"# {file_path.name}\n\n```yaml\n{raw_content}\n```"
            
            return {
                "success": True,
                "markdown": markdown_content,
                "raw_content": raw_content,
                "yaml_data": yaml_content,
                "processing_method": "yaml_parser"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse YAML file: {str(e)}"
            }
    
    def _process_json_document(self, file_path: Path) -> Dict[str, Any]:
        """Process JSON document."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
                json_content = json.loads(raw_content)
            
            # Convert JSON to markdown for display
            markdown_content = f"# {file_path.name}\n\n```json\n{json.dumps(json_content, indent=2)}\n```"
            
            return {
                "success": True,
                "markdown": markdown_content,
                "raw_content": raw_content,
                "json_data": json_content,
                "processing_method": "json_parser"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse JSON file: {str(e)}"
            }
    
    def _extract_structured_content(self, markdown: str, document_type: str) -> Dict[str, Any]:
        """
        Extract structured content based on document type.
        
        Args:
            markdown: Markdown content to analyze
            document_type: Type of document for specialized extraction
            
        Returns:
            Dictionary of structured content elements
        """
        structured = {
            "word_count": len(markdown.split()),
            "character_count": len(markdown),
            "sections": self._extract_sections(markdown),
            "tables": self._extract_tables(markdown),
            "lists": self._extract_lists(markdown)
        }
        
        # Document-type specific extractions
        if document_type == "lfa_draft":
            structured.update(self._extract_lfa_elements(markdown))
        elif document_type == "wp_description":
            structured.update(self._extract_wp_elements(markdown))
        elif document_type == "call_document":
            structured.update(self._extract_call_elements(markdown))
        
        return structured
    
    def _extract_sections(self, markdown: str) -> List[Dict[str, Any]]:
        """Extract section headers and content from markdown."""
        sections = []
        lines = markdown.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            if line.startswith('#'):
                # Save previous section
                if current_section:
                    sections.append({
                        "title": current_section,
                        "content": '\n'.join(current_content),
                        "word_count": len(' '.join(current_content).split())
                    })
                
                # Start new section
                current_section = line.strip('#').strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_section:
            sections.append({
                "title": current_section,
                "content": '\n'.join(current_content),
                "word_count": len(' '.join(current_content).split())
            })
        
        return sections
    
    def _extract_tables(self, markdown: str) -> List[Dict[str, Any]]:
        """Extract tables from markdown."""
        tables = []
        lines = markdown.split('\n')
        current_table = []
        in_table = False
        
        for line in lines:
            if '|' in line and line.strip():
                if not in_table:
                    in_table = True
                    current_table = []
                current_table.append(line.strip())
            else:
                if in_table and current_table:
                    # End of table
                    tables.append({
                        "content": '\n'.join(current_table),
                        "rows": len(current_table),
                        "columns": len(current_table[0].split('|')) if current_table else 0
                    })
                    current_table = []
                in_table = False
        
        # Handle table at end of document
        if current_table:
            tables.append({
                "content": '\n'.join(current_table),
                "rows": len(current_table),
                "columns": len(current_table[0].split('|')) if current_table else 0
            })
        
        return tables
    
    def _extract_lists(self, markdown: str) -> List[Dict[str, Any]]:
        """Extract lists from markdown."""
        lists = []
        lines = markdown.split('\n')
        current_list = []
        in_list = False
        
        for line in lines:
            if line.strip().startswith(('-', '*', '+')):
                if not in_list:
                    in_list = True
                    current_list = []
                current_list.append(line.strip())
            else:
                if in_list and current_list:
                    lists.append({
                        "content": '\n'.join(current_list),
                        "items": len(current_list),
                        "type": "unordered"
                    })
                    current_list = []
                in_list = False
        
        # Handle list at end of document
        if current_list:
            lists.append({
                "content": '\n'.join(current_list),
                "items": len(current_list),
                "type": "unordered"
            })
        
        return lists
    
    def _extract_lfa_elements(self, markdown: str) -> Dict[str, Any]:
        """Extract LFA-specific elements."""
        return {
            "objectives": self._find_content_after_headers(markdown, ["objective", "goal"]),
            "outcomes": self._find_content_after_headers(markdown, ["outcome", "result"]),
            "outputs": self._find_content_after_headers(markdown, ["output", "deliverable"]),
            "activities": self._find_content_after_headers(markdown, ["activity", "task"]),
            "assumptions": self._find_content_after_headers(markdown, ["assumption", "prerequisite"]),
            "risks": self._find_content_after_headers(markdown, ["risk", "threat"])
        }
    
    def _extract_wp_elements(self, markdown: str) -> Dict[str, Any]:
        """Extract Work Package-specific elements."""
        return {
            "wp_number": self._extract_wp_number(markdown),
            "wp_title": self._find_content_after_headers(markdown, ["title", "name"]),
            "objectives": self._find_content_after_headers(markdown, ["objective", "goal"]),
            "tasks": self._find_content_after_headers(markdown, ["task", "activity"]),
            "deliverables": self._find_content_after_headers(markdown, ["deliverable", "output"]),
            "milestones": self._find_content_after_headers(markdown, ["milestone", "checkpoint"]),
            "risks": self._find_content_after_headers(markdown, ["risk", "threat"]),
            "resources": self._find_content_after_headers(markdown, ["resource", "budget"])
        }
    
    def _extract_call_elements(self, markdown: str) -> Dict[str, Any]:
        """Extract funding call-specific elements."""
        return {
            "call_id": self._extract_call_id(markdown),
            "deadline": self._find_content_after_headers(markdown, ["deadline", "submission"]),
            "budget": self._find_content_after_headers(markdown, ["budget", "funding"]),
            "criteria": self._find_content_after_headers(markdown, ["criteria", "evaluation"]),
            "requirements": self._find_content_after_headers(markdown, ["requirement", "condition"])
        }
    
    def _find_content_after_headers(self, markdown: str, keywords: List[str]) -> List[str]:
        """Find content that appears after headers containing specific keywords."""
        content = []
        lines = markdown.split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('#') and any(keyword.lower() in line.lower() for keyword in keywords):
                # Found relevant header, collect content until next header
                section_content = []
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith('#'):
                        break
                    if lines[j].strip():
                        section_content.append(lines[j].strip())
                
                if section_content:
                    content.append('\n'.join(section_content))
        
        return content
    
    def _extract_wp_number(self, markdown: str) -> Optional[str]:
        """Extract work package number from markdown."""
        import re
        
        # Look for patterns like "WP1", "Work Package 1", etc.
        patterns = [
            r'WP\s*(\d+)',
            r'Work\s+Package\s+(\d+)',
            r'Package\s+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, markdown, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_call_id(self, markdown: str) -> Optional[str]:
        """Extract call ID from markdown."""
        import re
        
        # Look for call identifiers such as "PROGRAM-CALL-2025-IA-01"
        patterns = [
            r'([A-Z]+[-\w]*\d{4}[-\w]*)',
            r'(CBE[-\w]*\d{4}[-\w]*)',
            r'Call\s+ID[:\s]+([A-Z0-9-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, markdown, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file for version control."""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def batch_process_documents(self, documents: Dict[str, Path]) -> Dict[str, Any]:
        """
        Process multiple documents in batch.
        
        Args:
            documents: Dictionary mapping document types to file paths
            
        Returns:
            Dictionary of processed documents
        """
        results = {}
        
        for doc_type, doc_path in documents.items():
            print(f"Processing {doc_type}...")
            results[doc_type] = self.process_document(doc_path, doc_type)
        
        return results
