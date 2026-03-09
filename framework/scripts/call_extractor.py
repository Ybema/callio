#!/usr/bin/env python3
"""
Call Content Extractor

Extracts specific call content from large call documents based on project configuration.
Integrates with the pre-phase processing to automatically extract relevant call sections.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging


class CallExtractor:
    """Extracts specific call content from call documents."""
    
    def __init__(self, project_config: Dict[str, Any]):
        """
        Initialize the call extractor.
        
        Args:
            project_config: Project configuration dictionary
        """
        self.config = project_config
        self.call_config = project_config.get("call", {})
        self.extraction_config = project_config.get("extraction", {})
        self.processing_config = project_config.get("processing", {})
        
        self.logger = logging.getLogger(__name__)
    
    def extract_call_content(self, markdown_content: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract the call content using your proven approach from extract_call_content.py.
        
        Args:
            markdown_content: Full markdown content from the PDF
            
        Returns:
            Tuple of (extracted_call_content, extraction_metadata)
        """
        # Use your proven approach: find call section start, then extract to end
        call_start_index = self._find_call_section_start(markdown_content)
        call_content = self._extract_call_content_from_markdown(markdown_content, call_start_index)
        
        # Format the extracted content
        formatted_content = self._format_call_content(call_content)
        
        # Generate extraction metadata
        metadata = {
            "call_id": self.call_config.get("id", "unknown"),
            "extraction_method": "proven_approach",
            "start_line_index": call_start_index,
            "original_length": len(markdown_content),
            "extracted_length": len(formatted_content),
            "compression_ratio": len(formatted_content) / len(markdown_content) if markdown_content else 0,
            "sections_found": self._count_sections(formatted_content)
        }
        
        self.logger.info(f"Extracted call content: {len(formatted_content):,} chars from {len(markdown_content):,} chars")
        self.logger.info(f"Compression ratio: {metadata['compression_ratio']:.3f}")
        
        return formatted_content, metadata
    
    def _find_call_section_start(self, content: str, start_page: int = 44) -> int:
        """Find the start of the call section using your proven approach."""
        call_indicators = [
            'call for project proposals',
            'call topics',
            'specific requirements',
            'type of action'
        ]
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            for indicator in call_indicators:
                if indicator.lower() in line_lower:
                    self.logger.info(f"Call section found starting at line {i+1}: '{line.strip()[:50]}...'")
                    return i
        
        self.logger.warning("No call section start found, using beginning of document")
        return 0
    
    def _find_call_section_end(self, content: str, start_index: int) -> int:
        """Find the end of the call section using your proven approach."""
        lines = content.split('\n')
        
        # Start looking from the start_index
        for i in range(start_index, len(lines)):
            line = lines[i]
            line_lower = line.lower()
            
            # Check if we've reached the end of the call section
            # Look for indicators that we're moving to a different section
            if any(indicator in line_lower for indicator in [
                'annex', 'appendix', 'references', 'bibliography', 'end of call'
            ]):
                self.logger.info(f"Call section end found at line {i+1}: '{line.strip()[:50]}...'")
                return i
        
        self.logger.info("No call section end found, using end of document")
        return len(lines)
    
    def _extract_call_content_from_markdown(self, markdown_content: str, start_line_index: int) -> str:
        """Extract only the specific configured call topic and nothing more."""
        call_id = self.call_config.get("id", "")
        lines = markdown_content.split('\n')
        call_content = []
        
        # Find where our specific call topic's detailed content starts
        detailed_start = None
        for i in range(start_line_index, len(lines)):
            if call_id in lines[i] and any(keyword in ' '.join(lines[max(0, i-5):i+10]).lower() for keyword in [
                'type of action', 'innovation action', 'indicative budget'
            ]):
                detailed_start = i
                self.logger.info(f"Found detailed {call_id} content starting at line {i+1}: '{lines[i].strip()[:50]}...'")
                break
        
        if detailed_start is None:
            self.logger.warning(f"Could not find detailed content for {call_id}, using full extraction")
            detailed_start = start_line_index
        
        # Extract from the detailed start until we hit the next call topic
        for i in range(detailed_start, len(lines)):
            line = lines[i]
            call_content.append(line)
            
            # Stop when we reach the next call topic (different from our target)
            if (i > detailed_start + 10 and  # Skip first few lines to avoid false positives
                re.search(r'\b[A-Z]+(?:-[A-Z0-9]+){2,}\b', line) and
                call_id not in line):
                self.logger.info(f"Found next call topic at line {i+1}, stopping extraction: '{line.strip()[:50]}...'")
                # Don't include this line - stop before it
                call_content.pop()  # Remove the line we just added
                break
            
            # Also stop at document boundaries
            line_lower = line.lower().strip()
            if any(indicator in line_lower for indicator in [
                'annex', 'appendix', 'references', 'bibliography', 'end of call'
            ]):
                self.logger.info(f"Reached document boundary at line {i+1}: '{line.strip()[:50]}...'")
                break
        
        return "\n".join(call_content)
    
    
    def _format_call_content(self, content: str) -> str:
        """Format the extracted call content for better readability."""
        # Skip all processing that destroys table structure - use raw content!
        # The PDF extraction already has the table structure we need
        
        # Create header with metadata
        call_id = self.call_config.get("id", "unknown")
        call_title = self.call_config.get("title", "Unknown Call")
        
        header = f"""# {call_id}: {call_title}

**Call Type**: Innovation Action  
**Budget**: 7,000,000 EUR per project  
**TRL**: 6-7 at project end  

---

"""
        
        # Apply only the most minimal cleanup to preserve table structure
        formatted = self._minimal_cleanup(content)
        
        return header + formatted
    
    def _minimal_cleanup(self, content: str) -> str:
        """Apply formatting to improve readability while preserving table structure."""
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Fix spacing issues where words are glued together
            # Add space before capital letters that follow lowercase letters (camelCase fixes)
            line = re.sub(r'([a-z])([A-Z])', r'\1 \2', line)
            
            # Add space before "Type of action", "Innovation Action", etc.
            line = re.sub(r'([a-z])([A-Z][a-z]+\s+of\s+action)', r'\1\n\n\2', line)
            line = re.sub(r'(systems)(Type of action)', r'\1\n\n\2', line)
            line = re.sub(r'(Innovation Action)(Indicative budget)', r'\1\n\n\2', line)
            line = re.sub(r'(EUR 14 million)(Expected EU)', r'\1\n\n\2', line)
            line = re.sub(r'(different amounts)(TRL)', r'\1\n\n\2', line)
            line = re.sub(r'(end of the project\.)(Link to CBE JU)', r'\1\n\n\2', line)
            line = re.sub(r'(Specific Objectives)(Link to CBE JU SRIA)', r'\1\n\n\2', line)
            line = re.sub(r'(JU SRIA)(CBE JU KPIs)', r'\1\n\n\2', line)
            
            # Fix broken words with hyphens (from your proven approach)
            line = re.sub(r'\b(\w+)\s*-\s*(\w+)\b', r'\1-\2', line)
            
            # Remove page numbers and artifacts
            if re.match(r'^\s*\d+\s*$', line) or re.match(r'^Corrigendum of.*$', line):
                continue
                
            formatted_lines.append(line)
        
        # Join and clean up excessive whitespace
        result = '\n'.join(formatted_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
    
    def _restructure_pdf_content(self, content: str) -> str:
        """Preserve the natural table structure from PDF extraction with minimal formatting."""
        # The raw PDF extraction actually preserves table structure well!
        # Don't destroy it by over-processing - just clean up lightly
        
        lines = content.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines but preserve structure
            if not line:
                if formatted_lines and formatted_lines[-1] != '':
                    formatted_lines.append('')
                continue
            
            # Identify table headers and format them nicely
            if line in ['Type of action', 'Indicative budget', 'TRL']:
                formatted_lines.append(f'\n## {line}')
                formatted_lines.append('')
            elif line == 'Expected EU contribution per project':
                formatted_lines.append('\n## Expected EU Contribution per Project')
                formatted_lines.append('')
            elif line == 'Link to CBE JU Specific Objectives':
                formatted_lines.append('\n## Link to CBE JU Specific Objectives')
                formatted_lines.append('')
            elif line == 'Link to CBE JU SRIA':
                formatted_lines.append('\n## Link to CBE JU SRIA')
                formatted_lines.append('')
            elif line == 'CBE JU KPIs':
                formatted_lines.append('\n## CBE JU Key Performance Indicators')
                formatted_lines.append('')
            elif line == 'Expected outcomes':
                formatted_lines.append('\n## Expected Outcomes')
                formatted_lines.append('')
            elif line == 'Scope' and i < len(lines) - 1 and 'Whether exploiting' in lines[i+1]:
                formatted_lines.append('\n## Scope')
                formatted_lines.append('')
            # Format numbered items (KPIs, objectives)
            elif re.match(r'^\d+\.\d+:', line):
                formatted_lines.append(f'\n**{line}**')
            elif re.match(r'^\d+:', line) and not re.match(r'^\d+:\d+', line):
                formatted_lines.append(f'\n**{line}**')
            else:
                # Regular content line
                formatted_lines.append(line)
        
        # Join lines and clean up excessive whitespace
        result = '\n'.join(formatted_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
    
    def _clean_text(self, text: str) -> str:
        """Clean and improve text formatting using your proven approach."""
        # Stage 1: Basic cleanup (from format_call_document.py)
        # Fix broken words with hyphens
        text = re.sub(r'\b(\w+)\s*-\s*(\w+)\b', r'\1-\2', text)
        
        # Remove page numbers and artifacts
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^Corrigendum of.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\d+F\d+', '', text)  # Footnote references
        
        # Fix spacing issues
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\s+([,.;:])', r'\1', text)
        
        # Stage 2: Content structure improvements
        # Ensure proper paragraph breaks
        text = re.sub(r'(?<=[.!?])\s*\n(?=[A-Z])', '\n\n', text)
        
        # Fix broken sentences across lines
        text = re.sub(r'(?<=[a-z,])\s*\n(?=[a-z])', ' ', text)
        
        # Stage 3: Specific content fixes
        # Fix common typos and formatting issues
        text = re.sub(r'acce ptance', 'acceptance', text)
        text = re.sub(r'bio -based', 'bio-based', text)
        text = re.sub(r'cross -disciplinary', 'cross-disciplinary', text)
        text = re.sub(r'multi -trophic', 'multi-trophic', text)
        text = re.sub(r'cost -efficient', 'cost-efficient', text)
        text = re.sub(r'high -value', 'high-value', text)
        text = re.sub(r'state -of -the -art', 'state-of-the-art', text)
        
        # Stage 4: Final cleanup
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)
        
        return text.strip()
    
    def _structure_content(self, text: str) -> str:
        """Add structure to the content with proper headers and formatting."""
        # First, fix the major structural issues by adding line breaks
        # where key sections start
        key_sections = [
            ('Type of action', '\n\n## Type of Action\n'),
            ('Innovation Action', 'Innovation Action\n'),
            ('Indicative budget', '\n\n## Indicative Budget\n'),
            ('Expected EU contribution per project', '\n\n## Expected EU Contribution per Project\n'),
            ('TRL', '\n\n## Technology Readiness Level (TRL)\n'),
            ('Link to CBE JU Specific Objectives', '\n\n## Link to CBE JU Specific Objectives\n'),
            ('Link to CBE JU SRIA', '\n\n## Link to CBE JU SRIA\n'),
            ('CBE JU KPIs', '\n\n## CBE JU Key Performance Indicators\n'),
            ('Expected outcomes', '\n\n## Expected Outcomes\n'),
            ('Scope', '\n\n## Scope\n')
        ]
        
        for old_text, new_text in key_sections:
            # Use word boundaries to avoid partial matches
            text = re.sub(f'\\b{re.escape(old_text)}\\b', new_text, text, flags=re.IGNORECASE)
        
        # Format numbered objectives and KPIs with proper line breaks
        text = re.sub(r'(\d+\.\d+:\s*)', r'\n\n**\1** ', text)
        text = re.sub(r'(?<!\d)(\d+:\s*)', r'\n\n**\1** ', text)
        
        # Add line breaks before key phrases
        text = re.sub(r'(The total indicative budget)', r'\n\n\1', text)
        text = re.sub(r'(It is estimated that)', r'\n\n\1', text)
        text = re.sub(r'(TRL \d+-\d+)', r'\n\n\1', text)
        
        # Format bullet points
        text = re.sub(r'^\s*•\s*', '- ', text, flags=re.MULTILINE)
        
        # Clean up excessive whitespace but preserve structure
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)
        
        # Ensure proper spacing around headers
        text = re.sub(r'(#{1,6}[^\n]+)\n([^\n#])', r'\1\n\n\2', text)
        
        return text
    
    def _count_sections(self, content: str) -> int:
        """Count the number of sections in the formatted content."""
        return len(re.findall(r'^#{1,3}\s+', content, re.MULTILINE))
    
    
    def should_extract_call(self, content: str) -> bool:
        """
        Determine if this document contains the call we're looking for.
        
        Args:
            content: Document content to check
            
        Returns:
            True if the document contains our target call
        """
        call_id = self.call_config.get("id", "").lower()
        call_indicators = self.extraction_config.get("call_indicators", [])
        
        content_lower = content.lower()
        
        # Check for call ID
        if call_id and call_id in content_lower:
            return True
        
        # Check for call indicators
        indicators_found = sum(1 for indicator in call_indicators if indicator.lower() in content_lower)
        
        # Require at least 2 indicators to be confident
        return indicators_found >= 2


def load_project_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load simplified project configuration and convert to internal format.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Project configuration dictionary in internal format
    """
    if config_path is None:
        # Default to config/project_config.json
        config_path = Path(__file__).parent.parent / "config" / "project_config.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Project config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        simple_config = json.load(f)
    
    # Convert simplified config to internal format for backward compatibility
    call_id = simple_config.get("call_id", "CALL-ID-PLACEHOLDER")
    project_name = simple_config.get("project_name", "Project")
    
    return {
        "call": {"id": call_id},
        "project": {"name": project_name},
        # Hardcoded processing parameters (no longer user-configurable)
        "extraction": {
            "call_indicators": [call_id],
            "section_markers": {
                "end_indicators": ["annex", "appendix", "references", "bibliography", "end of call"]
            }
        },
        "processing": {"max_chars_call_context": 3000}
    }
