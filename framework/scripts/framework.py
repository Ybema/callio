#!/usr/bin/env python3
"""
project framework - Main Framework Controller

This module provides the main interface for the generic proposal support framework.
It orchestrates the three phases (LFA, Work Packages, Full Plan) and manages
configuration, version control, and output generation.
"""

import os
import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from .document_processor import DocumentProcessor
# from .review_engine import ReviewEngine  # Commented out - class doesn't exist
from .version_control import VersionControl
from .output_generator import OutputGenerator


class ProposalFramework:
    """
    Main framework controller for the generic proposal support tool.
    
    Manages the complete workflow from document ingestion through all three phases
    to final output generation, with full version control and traceability.
    """
    
    def __init__(self, project_root: Path, funding_type: str):
        """
        Initialize the framework for a specific funding type.
        
        Args:
            project_root: Root directory of the framework
            funding_type: Name of the funding type configuration to use
        """
        self.project_root = Path(project_root)
        self.funding_type = funding_type
        self.config = self._load_configuration(funding_type)
        
        # Load reference guides
        self.reference_guides = self._load_reference_guides()
        
        # Initialize core components with reference guides
        self.document_processor = DocumentProcessor(self.config, self.reference_guides)
        # self.review_engine = ReviewEngine(self.config)  # Commented out - class doesn't exist
        self.version_control = VersionControl(self.project_root / "snapshots")
        self.output_generator = OutputGenerator(self.config)
        
        # Runtime state
        self.current_phase = None
        self.session_id = None
        self.inputs = {}
        self.outputs = {}
    
    def _load_configuration(self, funding_type: str) -> Dict[str, Any]:
        """Load configuration for the specified funding type."""
        config_path = self.project_root / "config" / "funding_types" / f"{funding_type}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Load additional configuration files
        config['scoring_definitions'] = self._load_scoring_definitions()
        config['review_criteria'] = self._load_review_criteria()
        
        return config
    
    def _load_scoring_definitions(self, phase: str = None) -> Dict[str, Any]:
        """Load scoring definitions for the funding type and phase."""
        scoring_dir = self.project_root / "config" / "scoring_definitions"
        
        # Try phase-specific file first
        if phase:
            phase_file = scoring_dir / f"{self.funding_type}_phase_{phase}.md"
            if phase_file.exists():
                with open(phase_file, 'r', encoding='utf-8') as f:
                    return {"content": f.read(), "source": str(phase_file)}
        
        # Fall back to general funding type file
        scoring_file = scoring_dir / f"{self.funding_type}.md"
        if scoring_file.exists():
            with open(scoring_file, 'r', encoding='utf-8') as f:
                return {"content": f.read(), "source": str(scoring_file)}
        
        # Use default scoring
        default_file = scoring_dir / "default.md"
        if default_file.exists():
            with open(default_file, 'r', encoding='utf-8') as f:
                return {"content": f.read(), "source": str(default_file)}
        
        return {"content": "", "source": "none"}
    
    def _load_review_criteria(self, phase: str = None) -> Dict[str, Any]:
        """Load review criteria for the funding type and phase."""
        criteria_dir = self.project_root / "config" / "review_criteria"
        
        # Try phase-specific file first (human-readable markdown)
        if phase:
            phase_file = criteria_dir / f"{self.funding_type}_phase_{phase}.md"
            if phase_file.exists():
                with open(phase_file, 'r', encoding='utf-8') as f:
                    return {"content": f.read(), "source": str(phase_file), "format": "markdown"}
        
        # Fall back to YAML format
        criteria_file = criteria_dir / f"{self.funding_type}.yaml"
        if criteria_file.exists():
            with open(criteria_file, 'r', encoding='utf-8') as f:
                return {"data": yaml.safe_load(f), "source": str(criteria_file), "format": "yaml"}
        
        return {"content": "", "source": "none", "format": "none"}
    
    def _load_reference_guides(self) -> Dict[str, str]:
        """Load reference guides for framework operation."""
        reference_dir = self.project_root / "reference"
        guides = {}
        
        # Load MarkItDown guide
        markitdown_guide = reference_dir / "markitdown_guide.md"
        if markitdown_guide.exists():
            with open(markitdown_guide, 'r', encoding='utf-8') as f:
                guides['markitdown'] = f.read()
        
        # Load AI workflow guide
        ai_guide = reference_dir / "ai_workflow_guide.md"
        if ai_guide.exists():
            with open(ai_guide, 'r', encoding='utf-8') as f:
                guides['ai_workflow'] = f.read()
        
        return guides
    
    def start_session(self, review_mode: str = "python") -> str:
        """
        Start a new review session.
        
        Args:
            review_mode: Either "python" or "llm"
            
        Returns:
            Session ID for tracking this run
        """
        self.session_id = f"{self.funding_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.review_engine.set_mode(review_mode)
        
        print(f"🚀 Started project framework session: {self.session_id}")
        print(f"   Funding Type: {self.config['funding_info']['name']}")
        print(f"   Review Mode: {review_mode}")
        
        return self.session_id
    
    def ingest_documents(self, phase: str, documents: Dict[str, Path]) -> Dict[str, Any]:
        """
        Ingest and normalize documents for a specific phase.
        
        Args:
            phase: Phase name ("lfa", "work_packages", "full_plan")
            documents: Dictionary mapping document types to file paths
            
        Returns:
            Dictionary of processed documents with metadata
        """
        print(f"📄 Ingesting documents for Phase {phase.upper()}...")
        
        processed_docs = {}
        for doc_type, doc_path in documents.items():
            print(f"   Processing {doc_type}: {doc_path.name}")
            
            # Process document using MarkItDown and extract structured data
            result = self.document_processor.process_document(doc_path, doc_type)
            
            if result['success']:
                processed_docs[doc_type] = result
                print(f"   ✅ {doc_type}: {len(result['markdown'])} chars")
            else:
                print(f"   ❌ {doc_type}: {result['error']}")
                processed_docs[doc_type] = result
        
        self.inputs[phase] = processed_docs
        return processed_docs
    
    def run_phase(self, phase: str, documents: Dict[str, Path]) -> Dict[str, Any]:
        """
        Execute a complete phase of the framework.
        
        Args:
            phase: Phase name ("lfa", "work_packages", "full_plan")
            documents: Dictionary mapping document types to file paths
            
        Returns:
            Complete phase results including all outputs
        """
        if not self.session_id:
            raise RuntimeError("No active session. Call start_session() first.")
        
        self.current_phase = phase
        print(f"\n🔷 Executing Phase {phase.upper()}")
        print("=" * 50)
        
        # Load phase-specific configurations
        phase_scoring = self._load_scoring_definitions(phase)
        phase_criteria = self._load_review_criteria(phase)
        
        # Update config with phase-specific data
        phase_config = self.config.copy()
        phase_config['phase_scoring'] = phase_scoring
        phase_config['phase_criteria'] = phase_criteria
        
        # Step 1: Ingest documents
        processed_docs = self.ingest_documents(phase, documents)
        
        # Step 2: Run reviews
        print(f"🔍 Running {self.review_engine.mode} reviews...")
        review_results = self.review_engine.run_reviews(phase, processed_docs)
        
        # Step 3: Generate outputs
        print("📝 Generating outputs...")
        output_dir = self.project_root / "output"
        outputs = self.output_generator.generate_outputs(
            phase, processed_docs, review_results, output_dir
        )
        
        # Step 4: Create snapshot
        print("📸 Creating snapshot...")
        snapshot = self.version_control.create_snapshot(
            session_id=self.session_id,
            phase=phase,
            inputs=processed_docs,
            config=self.config,
            outputs=outputs
        )
        
        # Store results
        phase_results = {
            "phase": phase,
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "inputs": processed_docs,
            "reviews": review_results,
            "outputs": outputs,
            "snapshot": snapshot
        }
        
        self.outputs[phase] = phase_results
        
        print(f"✅ Phase {phase.upper()} completed successfully!")
        print(f"   Snapshot: {snapshot['id']}")
        print(f"   Outputs: {', '.join(outputs.keys())}")
        
        return phase_results
    
    def compare_snapshots(self, snapshot1_id: str, snapshot2_id: str) -> Dict[str, Any]:
        """
        Compare two snapshots to see what changed.
        
        Args:
            snapshot1_id: ID of first snapshot
            snapshot2_id: ID of second snapshot
            
        Returns:
            Comparison results showing differences
        """
        return self.version_control.compare_snapshots(snapshot1_id, snapshot2_id)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current session."""
        if not self.session_id:
            return {"error": "No active session"}
        
        return {
            "session_id": self.session_id,
            "funding_type": self.funding_type,
            "funding_name": self.config['funding_info']['name'],
            "review_mode": self.review_engine.mode,
            "phases_completed": list(self.outputs.keys()),
            "total_inputs": sum(len(phase_data['inputs']) for phase_data in self.outputs.values()),
            "total_outputs": sum(len(phase_data['outputs']) for phase_data in self.outputs.values()),
            "snapshots": [phase_data['snapshot']['id'] for phase_data in self.outputs.values()]
        }
    
    def list_available_funding_types(self) -> List[str]:
        """List all available funding type configurations."""
        config_dir = self.project_root / "config" / "funding_types"
        return [f.stem for f in config_dir.glob("*.yaml") if f.stem != "template"]
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate the current configuration for completeness."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required configuration sections
        required_sections = [
            "funding_info", "document_structure", "scoring", 
            "review_modes", "outputs", "validation"
        ]
        
        for section in required_sections:
            if section not in self.config:
                validation_results["errors"].append(f"Missing required section: {section}")
                validation_results["valid"] = False
        
        # Check funding info completeness
        if "funding_info" in self.config:
            required_funding_info = ["name", "type", "region", "language"]
            for field in required_funding_info:
                if field not in self.config["funding_info"]:
                    validation_results["warnings"].append(f"Missing funding_info field: {field}")
        
        # Check review mode availability
        if "review_modes" in self.config:
            if not self.config["review_modes"].get("python_rules", {}).get("enabled", False) and \
               not self.config["review_modes"].get("llm_contextual", {}).get("enabled", False):
                validation_results["errors"].append("At least one review mode must be enabled")
                validation_results["valid"] = False
        
        return validation_results


def main():
    """Command-line interface for the framework."""
    import argparse
    
    parser = argparse.ArgumentParser(description="project framework - Generic Proposal Support Tool")
    parser.add_argument("--funding-type", required=True, help="Funding type configuration to use")
    parser.add_argument("--mode", choices=["python", "llm"], default="python", help="Review mode")
    parser.add_argument("--phase", choices=["lfa", "work_packages", "full_plan"], help="Phase to run")
    parser.add_argument("--list-funding-types", action="store_true", help="List available funding types")
    parser.add_argument("--validate-config", action="store_true", help="Validate configuration")
    
    args = parser.parse_args()
    
    # Initialize framework
    framework_root = Path(__file__).parent.parent
    
    if args.list_funding_types:
        framework = ProposalFramework(framework_root, "template")  # Use template for listing
        funding_types = framework.list_available_funding_types()
        print("Available funding types:")
        for ft in funding_types:
            print(f"  - {ft}")
        return
    
    # Initialize with specified funding type
    framework = ProposalFramework(framework_root, args.funding_type)
    
    if args.validate_config:
        validation = framework.validate_configuration()
        print(f"Configuration validation: {'✅ VALID' if validation['valid'] else '❌ INVALID'}")
        if validation['errors']:
            print("Errors:")
            for error in validation['errors']:
                print(f"  - {error}")
        if validation['warnings']:
            print("Warnings:")
            for warning in validation['warnings']:
                print(f"  - {warning}")
        return
    
    # Start session
    session_id = framework.start_session(args.mode)
    print(f"\nSession started: {session_id}")
    
    # Show session summary
    summary = framework.get_session_summary()
    print(f"Funding Type: {summary['funding_name']}")
    print(f"Review Mode: {summary['review_mode']}")


if __name__ == "__main__":
    main()
