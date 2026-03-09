#!/usr/bin/env python3
"""
project framework - Output Generator

This module generates professional assessment reports by populating templates
with dynamic content from the review engine analysis.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class OutputGenerator:
    """
    Generates professional assessment reports using templates and dynamic content.
    
    Populates templates with analysis results to create the same high-quality
    output format as the original assessment.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the output generator with configuration."""
        self.config = config
        self.templates_dir = Path(__file__).parent.parent / "templates" / "output_templates"
    
    def generate_outputs(self, phase: str, processed_docs: Dict[str, Any], 
                        review_results: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
        """
        Generate all output formats for the specified phase.
        
        Args:
            phase: Phase name (e.g., "lfa")
            processed_docs: Processed documents from MarkItDown
            review_results: Analysis results from review engine
            output_dir: Directory to save outputs
            
        Returns:
            Dictionary mapping output types to file paths
        """
        outputs = {}
        
        if phase == "lfa":
            # Generate LFA assessment report
            lfa_outputs = self._generate_lfa_assessment(processed_docs, review_results, output_dir)
            outputs.update(lfa_outputs)
        
        return outputs
    
    def _generate_lfa_assessment(self, processed_docs: Dict[str, Any], 
                               review_results: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
        """Generate LFA assessment report using the original template structure."""
        
        # Load the assessment template
        template_path = self.templates_dir / "lfa_assessment_template.md"
        if not template_path.exists():
            raise FileNotFoundError(f"LFA assessment template not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Populate template with dynamic content
        populated_content = self._populate_lfa_template(template_content, processed_docs, review_results)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lfa_review_{timestamp}.md"
        output_path = output_dir / filename
        
        # Save populated content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(populated_content)
        
        # Generate JSON output
        json_output = self._generate_json_output(review_results, processed_docs)
        json_filename = f"lfa_review_{timestamp}.json"
        json_path = output_dir / json_filename
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        
        return {
            "markdown": str(output_path),
            "json": str(json_path)
        }
    
    def _populate_lfa_template(self, template: str, processed_docs: Dict[str, Any], 
                             review_results: Dict[str, Any]) -> str:
        """Populate the LFA assessment template with dynamic content."""
        
        # Extract analysis data
        overall_score = review_results.get("overall_quality_score", 0)
        quality_level = review_results.get("quality_level", "UNKNOWN")
        executive_summary = review_results.get("executive_summary", "")
        key_findings = review_results.get("key_findings", [])
        detailed_analysis = review_results.get("detailed_analysis", {})
        recommendations = review_results.get("recommendations", {})
        assessment_criteria = review_results.get("assessment_criteria", {})
        
        # Get project name from config
        project_name = self.config.get("funding_info", {}).get("name", "Unknown Project")
        
        # Replace template placeholders with dynamic content
        populated = template
        
        # Header information
        populated = populated.replace("{{PROJECT_NAME}}", project_name)
        populated = populated.replace("{{ANALYSIS_DATE}}", datetime.now().strftime("%B %d, %Y"))
        populated = populated.replace("{{ANALYSIS_VERSION}}", "v1.0")
        populated = populated.replace("{{ANALYSIS_METHOD}}", review_results.get("analysis_method", "intelligent_content_analysis"))
        populated = populated.replace("{{ANALYST}}", "AI Analysis Engine")
        
        # Overall assessment
        populated = populated.replace("{{OVERALL_SCORE}}", f"{overall_score}%")
        populated = populated.replace("{{OVERALL_RATING}}", quality_level)
        populated = populated.replace("{{BRIEF_ASSESSMENT}}", "Solid foundation with targeted improvements needed")
        populated = populated.replace("{{EXECUTIVE_SUMMARY}}", executive_summary)
        
        # Key findings
        populated = self._populate_key_findings(populated, key_findings)
        
        # Detailed analysis sections
        populated = self._populate_structured_analysis(populated, detailed_analysis)
        
        # Recommendations
        populated = self._populate_structured_recommendations(populated, recommendations)
        
        return populated
    
    def _populate_key_findings(self, content: str, key_findings: List[str]) -> str:
        """Populate key findings section."""
        if len(key_findings) >= 4:
            # Extract specific findings
            strongest = key_findings[0] if key_findings else "Analysis in progress"
            weakest = key_findings[1] if len(key_findings) > 1 else "Analysis in progress"
            critical_gap = key_findings[2] if len(key_findings) > 2 else "Analysis in progress"
            innovation = key_findings[3] if len(key_findings) > 3 else "Analysis in progress"
            
            # Extract scores and descriptions
            strongest_parts = strongest.split(" – ")
            strongest_section = strongest_parts[0].replace("**Strongest Section**: ", "")
            strongest_score = strongest_parts[1].split("%")[0] if len(strongest_parts) > 1 else "0"
            strongest_desc = strongest_parts[1].split("(")[1].replace(")", "") if len(strongest_parts) > 1 and "(" in strongest_parts[1] else "Analysis in progress"
            
            weakest_parts = weakest.split(" – ")
            weakest_section = weakest_parts[0].replace("**Most Improvement Needed**: ", "")
            weakest_score = weakest_parts[1].split("%")[0] if len(weakest_parts) > 1 else "0"
            weakest_desc = weakest_parts[1].split("(")[1].replace(")", "") if len(weakest_parts) > 1 and "(" in weakest_parts[1] else "Analysis in progress"
            
            critical_gap_text = critical_gap.replace("**Critical Gap**: ", "")
            innovation_text = innovation.replace("**Innovation Highlight**: ", "")
            
            content = content.replace("{{STRONGEST_SECTION}}", strongest_section)
            content = content.replace("{{STRONGEST_SCORE}}", strongest_score)
            content = content.replace("{{WHY_STRONG}}", strongest_desc)
            content = content.replace("{{WEAKEST_SECTION}}", weakest_section)
            content = content.replace("{{WEAKEST_SCORE}}", weakest_score)
            content = content.replace("{{WHY_WEAK}}", weakest_desc)
            content = content.replace("{{CRITICAL_GAP}}", critical_gap_text)
            content = content.replace("{{INNOVATION_HIGHLIGHT}}", innovation_text)
        
        return content
    
    def _populate_structured_analysis(self, content: str, detailed_analysis: Dict[str, Any]) -> str:
        """Populate structured analysis sections."""
        
        # Call Alignment section
        call_alignment = detailed_analysis.get("call_alignment", {})
        call_score = call_alignment.get("score", 0)
        call_quality = call_alignment.get("quality", "UNKNOWN")
        call_criteria = call_alignment.get("criteria", {})
        call_strengths = call_alignment.get("strengths", [])
        call_improvements = call_alignment.get("improvements", [])
        
        content = content.replace("{{CALL_ALIGNMENT_SCORE}}", f"{call_score}%")
        content = content.replace("{{CALL_ALIGNMENT_RATING}}", call_quality)
        
        # Call alignment criteria
        content = content.replace("{{CA1_SCORE}}", f"{call_criteria.get('ca1_call_objectives', {}).get('score', 0)}%")
        content = content.replace("{{CA1_STATUS}}", call_criteria.get('ca1_call_objectives', {}).get('status', 'UNKNOWN'))
        content = content.replace("{{CA1_FEEDBACK}}", call_criteria.get('ca1_call_objectives', {}).get('feedback', 'Analysis in progress'))
        
        content = content.replace("{{CA2_SCORE}}", f"{call_criteria.get('ca2_scope_fit', {}).get('score', 0)}%")
        content = content.replace("{{CA2_STATUS}}", call_criteria.get('ca2_scope_fit', {}).get('status', 'UNKNOWN'))
        content = content.replace("{{CA2_FEEDBACK}}", call_criteria.get('ca2_scope_fit', {}).get('feedback', 'Analysis in progress'))
        
        content = content.replace("{{CA3_SCORE}}", f"{call_criteria.get('ca3_outcomes_impacts', {}).get('score', 0)}%")
        content = content.replace("{{CA3_STATUS}}", call_criteria.get('ca3_outcomes_impacts', {}).get('status', 'UNKNOWN'))
        content = content.replace("{{CA3_FEEDBACK}}", call_criteria.get('ca3_outcomes_impacts', {}).get('feedback', 'Analysis in progress'))
        
        content = content.replace("{{CA4_SCORE}}", f"{call_criteria.get('ca4_eval_criteria', {}).get('score', 0)}%")
        content = content.replace("{{CA4_STATUS}}", call_criteria.get('ca4_eval_criteria', {}).get('status', 'UNKNOWN'))
        content = content.replace("{{CA4_FEEDBACK}}", call_criteria.get('ca4_eval_criteria', {}).get('feedback', 'Analysis in progress'))
        
        content = content.replace("{{CA5_SCORE}}", f"{call_criteria.get('ca5_eligibility', {}).get('score', 0)}%")
        content = content.replace("{{CA5_STATUS}}", call_criteria.get('ca5_eligibility', {}).get('status', 'UNKNOWN'))
        content = content.replace("{{CA5_FEEDBACK}}", call_criteria.get('ca5_eligibility', {}).get('feedback', 'Analysis in progress'))
        
        content = content.replace("{{CA6_SCORE}}", f"{call_criteria.get('ca6_terminology', {}).get('score', 0)}%")
        content = content.replace("{{CA6_STATUS}}", call_criteria.get('ca6_terminology', {}).get('status', 'UNKNOWN'))
        content = content.replace("{{CA6_FEEDBACK}}", call_criteria.get('ca6_terminology', {}).get('feedback', 'Analysis in progress'))
        
        # Call alignment strengths and improvements
        content = content.replace("{{CALL_ALIGNMENT_STRENGTH_1}}", call_strengths[0] if len(call_strengths) > 0 else "Analysis in progress")
        content = content.replace("{{CALL_ALIGNMENT_STRENGTH_2}}", call_strengths[1] if len(call_strengths) > 1 else "Analysis in progress")
        content = content.replace("{{CALL_ALIGNMENT_IMPROVEMENT_1}}", call_improvements[0] if len(call_improvements) > 0 else "Analysis in progress")
        content = content.replace("{{CALL_ALIGNMENT_IMPROVEMENT_2}}", call_improvements[1] if len(call_improvements) > 1 else "Analysis in progress")
        
        # Internal Consistency section
        internal_consistency = detailed_analysis.get("internal_consistency", {})
        internal_score = internal_consistency.get("score", 0)
        internal_quality = internal_consistency.get("quality", "UNKNOWN")
        internal_criteria = internal_consistency.get("criteria", {})
        internal_strengths = internal_consistency.get("strengths", [])
        internal_improvements = internal_consistency.get("improvements", [])
        
        content = content.replace("{{INTERNAL_CONSISTENCY_SCORE}}", f"{internal_score}%")
        content = content.replace("{{INTERNAL_CONSISTENCY_RATING}}", internal_quality)
        
        # Internal consistency criteria (LC1-LC8)
        for i in range(1, 9):
            lc_key = f"lc{i}_" + ["hierarchy_coherence", "traceability", "kpi_smartness", "temporal_coherence", "risk_linkage", "terminology", "duplication", "completeness"][i-1]
            content = content.replace(f"{{LC{i}_SCORE}}", f"{internal_criteria.get(lc_key, {}).get('score', 0)}%")
            content = content.replace(f"{{LC{i}_STATUS}}", internal_criteria.get(lc_key, {}).get('status', 'UNKNOWN'))
            content = content.replace(f"{{LC{i}_FEEDBACK}}", internal_criteria.get(lc_key, {}).get('feedback', 'Analysis in progress'))
        
        # Internal consistency strengths and improvements
        content = content.replace("{{INTERNAL_CONSISTENCY_STRENGTH_1}}", internal_strengths[0] if len(internal_strengths) > 0 else "Analysis in progress")
        content = content.replace("{{INTERNAL_CONSISTENCY_STRENGTH_2}}", internal_strengths[1] if len(internal_strengths) > 1 else "Analysis in progress")
        content = content.replace("{{INTERNAL_CONSISTENCY_IMPROVEMENT_1}}", internal_improvements[0] if len(internal_improvements) > 0 else "Analysis in progress")
        content = content.replace("{{INTERNAL_CONSISTENCY_IMPROVEMENT_2}}", internal_improvements[1] if len(internal_improvements) > 1 else "Analysis in progress")
        
        # Content Quality section
        content_quality = detailed_analysis.get("content_quality", {})
        content_score = content_quality.get("score", 0)
        content_quality_rating = content_quality.get("quality", "UNKNOWN")
        content_criteria = content_quality.get("criteria", {})
        content_strengths = content_quality.get("strengths", [])
        content_improvements = content_quality.get("improvements", [])
        
        content = content.replace("{{CONTENT_SCORE}}", f"{content_score}%")
        content = content.replace("{{CONTENT_RATING}}", content_quality_rating)
        
        # Content quality criteria (CQ1-CQ4)
        cq_keys = ["cq1_readability", "cq2_specificity", "cq3_writing", "cq4_terminology"]
        for i, cq_key in enumerate(cq_keys, 1):
            content = content.replace(f"{{CQ{i}_SCORE}}", f"{content_criteria.get(cq_key, {}).get('score', 0)}%")
            content = content.replace(f"{{CQ{i}_STATUS}}", content_criteria.get(cq_key, {}).get('status', 'UNKNOWN'))
            content = content.replace(f"{{CQ{i}_FEEDBACK}}", content_criteria.get(cq_key, {}).get('feedback', 'Analysis in progress'))
        
        # Content quality strengths and improvements
        content = content.replace("{{CONTENT_STRENGTH_1}}", content_strengths[0] if len(content_strengths) > 0 else "Analysis in progress")
        content = content.replace("{{CONTENT_STRENGTH_2}}", content_strengths[1] if len(content_strengths) > 1 else "Analysis in progress")
        content = content.replace("{{CONTENT_IMPROVEMENT_1}}", content_improvements[0] if len(content_improvements) > 0 else "Analysis in progress")
        content = content.replace("{{CONTENT_IMPROVEMENT_2}}", content_improvements[1] if len(content_improvements) > 1 else "Analysis in progress")
        
        return content
    
    def _populate_structured_recommendations(self, content: str, recommendations: Dict[str, Any]) -> str:
        """Populate structured recommendations section."""
        
        priority_improvements = recommendations.get("priority_improvements", [])
        next_steps = recommendations.get("next_steps", [])
        
        # Priority improvements
        content = content.replace("{{PRIORITY_IMPROVEMENT_1}}", priority_improvements[0] if len(priority_improvements) > 0 else "Continue quality improvement")
        content = content.replace("{{PRIORITY_IMPROVEMENT_2}}", priority_improvements[1] if len(priority_improvements) > 1 else "Strengthen methodology application")
        content = content.replace("{{PRIORITY_IMPROVEMENT_3}}", priority_improvements[2] if len(priority_improvements) > 2 else "Enhance content quality")
        
        # Next steps
        content = content.replace("{{NEXT_STEP_1}}", next_steps[0] if len(next_steps) > 0 else "Review and refine logical framework structure")
        content = content.replace("{{NEXT_STEP_2}}", next_steps[1] if len(next_steps) > 1 else "Strengthen methodology application")
        content = content.replace("{{NEXT_STEP_3}}", next_steps[2] if len(next_steps) > 2 else "Enhance content quality")
        
        return content
    
    def _populate_intelligent_analysis(self, content: str, detailed_analysis: Dict[str, Any]) -> str:
        """Populate detailed analysis sections with intelligent analysis results."""
        
        # Document Structure section
        structure_analysis = detailed_analysis.get("document_structure", {})
        structure_score = structure_analysis.get("score", 0)
        structure_quality = structure_analysis.get("quality", "UNKNOWN")
        structure_criteria = structure_analysis.get("criteria", {})
        structure_strengths = structure_analysis.get("strengths", [])
        structure_improvements = structure_analysis.get("improvements", [])
        
        # Replace structure section
        content = content.replace("{{GOAL_SCORE}}", f"{structure_score}%")
        content = content.replace("{{GOAL_QUALITY}}", structure_quality)
        
        # Structure criteria table
        structure_criteria_table = self._create_criteria_table(structure_criteria)
        content = content.replace("{{GOAL_CRITERIA_TABLE}}", structure_criteria_table)
        
        # Structure strengths
        structure_strengths_text = "\n".join([f"- {strength}" for strength in structure_strengths])
        content = content.replace("{{GOAL_STRENGTHS}}", structure_strengths_text)
        
        # Structure improvements
        structure_improvements_text = "\n".join([f"- {improvement}" for improvement in structure_improvements])
        content = content.replace("{{GOAL_IMPROVEMENTS}}", structure_improvements_text)
        
        # LFA Methodology section
        methodology_analysis = detailed_analysis.get("lfa_methodology", {})
        methodology_score = methodology_analysis.get("score", 0)
        methodology_quality = methodology_analysis.get("quality", "UNKNOWN")
        methodology_criteria = methodology_analysis.get("criteria", {})
        methodology_strengths = methodology_analysis.get("strengths", [])
        methodology_improvements = methodology_analysis.get("improvements", [])
        
        # Replace methodology section
        content = content.replace("{{PURPOSE_SCORE}}", f"{methodology_score}%")
        content = content.replace("{{PURPOSE_QUALITY}}", methodology_quality)
        
        # Methodology criteria table
        methodology_criteria_table = self._create_criteria_table(methodology_criteria)
        content = content.replace("{{PURPOSE_CRITERIA_TABLE}}", methodology_criteria_table)
        
        # Methodology strengths
        methodology_strengths_text = "\n".join([f"- {strength}" for strength in methodology_strengths])
        content = content.replace("{{PURPOSE_STRENGTHS}}", methodology_strengths_text)
        
        # Methodology improvements
        methodology_improvements_text = "\n".join([f"- {improvement}" for improvement in methodology_improvements])
        content = content.replace("{{PURPOSE_IMPROVEMENTS}}", methodology_improvements_text)
        
        # Content Quality section
        content_analysis = detailed_analysis.get("content_quality", {})
        content_score = content_analysis.get("score", 0)
        content_quality = content_analysis.get("quality", "UNKNOWN")
        content_criteria = content_analysis.get("criteria", {})
        content_strengths = content_analysis.get("strengths", [])
        content_improvements = content_analysis.get("improvements", [])
        
        # Replace content section
        content = content.replace("{{RESULTS_SCORE}}", f"{content_score}%")
        content = content.replace("{{RESULTS_QUALITY}}", content_quality)
        
        # Content criteria table
        content_criteria_table = self._create_criteria_table(content_criteria)
        content = content.replace("{{RESULTS_CRITERIA_TABLE}}", content_criteria_table)
        
        # Content strengths
        content_strengths_text = "\n".join([f"- {strength}" for strength in content_strengths])
        content = content.replace("{{RESULTS_STRENGTHS}}", content_strengths_text)
        
        # Content improvements
        content_improvements_text = "\n".join([f"- {improvement}" for improvement in content_improvements])
        content = content.replace("{{RESULTS_IMPROVEMENTS}}", content_improvements_text)
        
        return content
    
    def _populate_recommendations(self, content: str, recommendations: Dict[str, Any]) -> str:
        """Populate recommendations section."""
        
        priority_improvements = recommendations.get("priority_improvements", [])
        next_steps = recommendations.get("next_steps", [])
        
        # Priority improvements
        priority_text = "\n".join([f"{i+1}. {improvement}" for i, improvement in enumerate(priority_improvements)])
        content = content.replace("{{PRIORITY_IMPROVEMENTS}}", priority_text)
        
        # Next steps
        next_steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(next_steps)])
        content = content.replace("{{NEXT_STEPS}}", next_steps_text)
        
        return content
    
    def _populate_assessment_criteria(self, content: str, assessment_criteria: Dict[str, Any]) -> str:
        """Populate assessment criteria tables."""
        
        # This method would populate any additional criteria tables if needed
        # For now, the main criteria are handled in the detailed analysis section
        
        return content
    
    def _create_criteria_table(self, criteria: Dict[str, Any]) -> str:
        """Create a criteria assessment table."""
        if not criteria:
            return "No criteria data available."
        
        table_rows = []
        for criterion_name, criterion_data in criteria.items():
            score = criterion_data.get("score", 0)
            quality = criterion_data.get("quality", "UNKNOWN")
            
            # Format criterion name for display
            display_name = criterion_name.replace("_", " ").title()
            
            table_rows.append(f"| {display_name} | {score}% | {quality} |")
        
        if not table_rows:
            return "No criteria data available."
        
        # Create table with headers
        table = "| Criterion | Score | Quality | Comments |\n"
        table += "|-----------|-------|---------|----------|\n"
        table += "\n".join(table_rows)
        
        return table
    
    def _generate_json_output(self, review_results: Dict[str, Any], processed_docs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured JSON output."""
        
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "analysis_method": review_results.get("analysis_method", "original_lfa_methodology"),
                "project_name": self.config.get("funding_info", {}).get("name", "Unknown Project"),
                "funding_type": self.config.get("funding_info", {}).get("type", "Unknown")
            },
            "overall_assessment": {
                "quality_score": review_results.get("overall_quality_score", 0),
                "quality_level": review_results.get("quality_level", "UNKNOWN"),
                "executive_summary": review_results.get("executive_summary", ""),
                "key_findings": review_results.get("key_findings", [])
            },
            "detailed_analysis": review_results.get("detailed_analysis", {}),
            "recommendations": review_results.get("recommendations", {}),
            "assessment_criteria": review_results.get("assessment_criteria", {}),
            "document_metadata": {
                "lfa_document": {
                    "processed": processed_docs.get("lfa_draft", {}).get("success", False),
                    "word_count": processed_docs.get("lfa_draft", {}).get("structured_content", {}).get("word_count", 0),
                    "processing_method": processed_docs.get("lfa_draft", {}).get("processing_method", "unknown")
                },
                "call_document": {
                    "processed": processed_docs.get("call_document", {}).get("success", False),
                    "word_count": processed_docs.get("call_document", {}).get("structured_content", {}).get("word_count", 0),
                    "processing_method": processed_docs.get("call_document", {}).get("processing_method", "unknown")
                }
            }
        }
