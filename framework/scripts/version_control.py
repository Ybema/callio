#!/usr/bin/env python3
"""
project framework - Version Control

This module provides snapshot-based version control for complete traceability
of all inputs, configurations, and outputs.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class VersionControl:
    """
    Snapshot-based version control system.
    
    Creates complete snapshots of each run including inputs, configuration,
    and outputs for full traceability and reproducibility.
    """
    
    def __init__(self, snapshots_dir: Path):
        """
        Initialize the version control system.
        
        Args:
            snapshots_dir: Directory to store snapshots
        """
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    def create_snapshot(self, session_id: str, phase: str, inputs: Dict[str, Any], 
                       config: Dict[str, Any], outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a complete snapshot of a phase execution.
        
        Args:
            session_id: Current session ID
            phase: Phase name
            inputs: Input documents and their processed content
            config: Configuration used for this run
            outputs: Generated outputs
            
        Returns:
            Snapshot metadata
        """
        timestamp = datetime.now().isoformat()
        snapshot_id = f"{session_id}_{phase}_{datetime.now().strftime('%H%M%S')}"
        
        # Create snapshot data
        snapshot_data = {
            "id": snapshot_id,
            "session_id": session_id,
            "phase": phase,
            "timestamp": timestamp,
            "inputs": self._process_inputs_for_snapshot(inputs),
            "config": self._process_config_for_snapshot(config),
            "outputs": outputs,
            "metadata": {
                "framework_version": "1.0.0",
                "python_version": self._get_python_version(),
                "dependencies": self._get_dependencies_info()
            }
        }
        
        # Calculate snapshot hash
        snapshot_hash = self._calculate_snapshot_hash(snapshot_data)
        snapshot_data["hash"] = snapshot_hash
        
        # Save snapshot
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, indent=2, default=str)
        
        print(f"📸 Snapshot created: {snapshot_id}")
        print(f"   Hash: {snapshot_hash[:12]}...")
        
        return {
            "id": snapshot_id,
            "hash": snapshot_hash,
            "file": str(snapshot_file),
            "timestamp": timestamp
        }
    
    def _process_inputs_for_snapshot(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process inputs for snapshot storage."""
        processed_inputs = {}
        
        for doc_type, doc_data in inputs.items():
            if doc_data.get("success", False):
                processed_inputs[doc_type] = {
                    "file_path": doc_data.get("file_path"),
                    "file_hash": doc_data.get("file_hash"),
                    "file_size": doc_data.get("file_size"),
                    "document_type": doc_data.get("document_type"),
                    "processing_method": doc_data.get("processing_method"),
                    "processed_at": doc_data.get("processed_at"),
                    "content_length": len(doc_data.get("markdown", "")),
                    "structured_summary": {
                        "word_count": doc_data.get("structured_content", {}).get("word_count", 0),
                        "sections_count": len(doc_data.get("structured_content", {}).get("sections", [])),
                        "tables_count": len(doc_data.get("structured_content", {}).get("tables", [])),
                        "lists_count": len(doc_data.get("structured_content", {}).get("lists", []))
                    }
                }
            else:
                processed_inputs[doc_type] = {
                    "status": "failed",
                    "error": doc_data.get("error"),
                    "file_path": doc_data.get("file_path")
                }
        
        return processed_inputs
    
    def _process_config_for_snapshot(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process configuration for snapshot storage."""
        # Create a clean copy of config without sensitive data
        clean_config = {}
        
        for key, value in config.items():
            if key == "review_modes" and isinstance(value, dict):
                # Remove sensitive API keys from config
                clean_review_modes = {}
                for mode_key, mode_value in value.items():
                    if isinstance(mode_value, dict):
                        clean_mode = mode_value.copy()
                        if "providers" in clean_mode:
                            clean_providers = []
                            for provider in clean_mode["providers"]:
                                clean_provider = provider.copy()
                                if "api_key_env" in clean_provider:
                                    clean_provider["api_key_env"] = "[REDACTED]"
                                clean_providers.append(clean_provider)
                            clean_mode["providers"] = clean_providers
                        clean_review_modes[mode_key] = clean_mode
                    else:
                        clean_review_modes[mode_key] = mode_value
                clean_config[key] = clean_review_modes
            else:
                clean_config[key] = value
        
        return clean_config
    
    def _calculate_snapshot_hash(self, snapshot_data: Dict[str, Any]) -> str:
        """Calculate hash of snapshot data."""
        # Create a deterministic string representation
        snapshot_str = json.dumps(snapshot_data, sort_keys=True, default=str)
        return hashlib.sha256(snapshot_str.encode()).hexdigest()
    
    def _get_python_version(self) -> str:
        """Get Python version info."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def _get_dependencies_info(self) -> Dict[str, str]:
        """Get information about key dependencies."""
        deps = {}
        
        try:
            import markitdown
            deps["markitdown"] = getattr(markitdown, "__version__", "unknown")
        except ImportError:
            deps["markitdown"] = "not_installed"
        
        try:
            import yaml
            deps["pyyaml"] = getattr(yaml, "__version__", "unknown")
        except ImportError:
            deps["pyyaml"] = "not_installed"
        
        return deps
    
    def load_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Load a snapshot by ID.
        
        Args:
            snapshot_id: Snapshot ID to load
            
        Returns:
            Snapshot data
        """
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        
        if not snapshot_file.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")
        
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_snapshots(self, session_id: str = None) -> List[Dict[str, Any]]:
        """
        List available snapshots.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            List of snapshot metadata
        """
        snapshots = []
        
        for snapshot_file in self.snapshots_dir.glob("*.json"):
            try:
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    snapshot_data = json.load(f)
                
                if session_id is None or snapshot_data.get("session_id") == session_id:
                    snapshots.append({
                        "id": snapshot_data["id"],
                        "session_id": snapshot_data["session_id"],
                        "phase": snapshot_data["phase"],
                        "timestamp": snapshot_data["timestamp"],
                        "hash": snapshot_data["hash"]
                    })
            except (json.JSONDecodeError, KeyError):
                # Skip invalid snapshot files
                continue
        
        # Sort by timestamp, newest first
        snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
        return snapshots
    
    def compare_snapshots(self, snapshot1_id: str, snapshot2_id: str) -> Dict[str, Any]:
        """
        Compare two snapshots to identify differences.
        
        Args:
            snapshot1_id: First snapshot ID
            snapshot2_id: Second snapshot ID
            
        Returns:
            Comparison results
        """
        snapshot1 = self.load_snapshot(snapshot1_id)
        snapshot2 = self.load_snapshot(snapshot2_id)
        
        comparison = {
            "snapshot1": {
                "id": snapshot1_id,
                "timestamp": snapshot1["timestamp"],
                "phase": snapshot1["phase"]
            },
            "snapshot2": {
                "id": snapshot2_id,
                "timestamp": snapshot2["timestamp"],
                "phase": snapshot2["phase"]
            },
            "differences": {}
        }
        
        # Compare inputs
        input_diff = self._compare_inputs(snapshot1.get("inputs", {}), snapshot2.get("inputs", {}))
        if input_diff:
            comparison["differences"]["inputs"] = input_diff
        
        # Compare configuration
        config_diff = self._compare_configs(snapshot1.get("config", {}), snapshot2.get("config", {}))
        if config_diff:
            comparison["differences"]["config"] = config_diff
        
        # Compare outputs
        output_diff = self._compare_outputs(snapshot1.get("outputs", {}), snapshot2.get("outputs", {}))
        if output_diff:
            comparison["differences"]["outputs"] = output_diff
        
        return comparison
    
    def _compare_inputs(self, inputs1: Dict[str, Any], inputs2: Dict[str, Any]) -> Dict[str, Any]:
        """Compare inputs between two snapshots."""
        differences = {}
        
        all_docs = set(inputs1.keys()) | set(inputs2.keys())
        
        for doc_type in all_docs:
            if doc_type not in inputs1:
                differences[doc_type] = {"status": "added_in_snapshot2"}
            elif doc_type not in inputs2:
                differences[doc_type] = {"status": "removed_in_snapshot2"}
            else:
                doc1 = inputs1[doc_type]
                doc2 = inputs2[doc_type]
                
                if doc1.get("file_hash") != doc2.get("file_hash"):
                    differences[doc_type] = {
                        "status": "content_changed",
                        "hash1": doc1.get("file_hash"),
                        "hash2": doc2.get("file_hash")
                    }
        
        return differences
    
    def _compare_configs(self, config1: Dict[str, Any], config2: Dict[str, Any]) -> Dict[str, Any]:
        """Compare configurations between two snapshots."""
        # Simple comparison - in a full implementation, this would be more sophisticated
        if config1 != config2:
            return {"status": "configuration_changed"}
        return {}
    
    def _compare_outputs(self, outputs1: Dict[str, Any], outputs2: Dict[str, Any]) -> Dict[str, Any]:
        """Compare outputs between two snapshots."""
        # Simple comparison - in a full implementation, this would be more sophisticated
        if outputs1 != outputs2:
            return {"status": "outputs_changed"}
        return {}
