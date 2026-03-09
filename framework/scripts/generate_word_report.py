#!/usr/bin/env python3
"""
Generate Word report from JSON review results.

Usage:
    python scripts/generate_word_report.py <json_file> [output_file]
    
Examples:
    # Generate Word report from latest JSON file
    python scripts/generate_word_report.py
    
    # Generate Word report from specific JSON file
    python scripts/generate_word_report.py output/phase_a/review_results/lfa_review_result_20250925_003809.json
    
    # Generate Word report with custom output name
    python scripts/generate_word_report.py output/phase_a/review_results/lfa_review_result_20250925_003809.json my_report.docx
"""

import sys
import json
import pathlib
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def find_latest_json_file():
    """Find the most recent JSON review result file."""
    review_results_dir = Path("output/phase_a/review_results")
    if not review_results_dir.exists():
        print("❌ No review results directory found")
        return None
    
    json_files = list(review_results_dir.glob("lfa_review_result_*.json"))
    if not json_files:
        print("❌ No JSON review result files found")
        return None
    
    # Sort by modification time, most recent first
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    return latest_file

def generate_word_report(json_file_path, output_file_path=None):
    """Generate Word report from JSON review results."""
    try:
        # Import here to avoid import errors if not needed
        from scripts.review_engine.word_export import export_review_to_word
        
        # Load JSON data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            review_data = json.load(f)
        
        # Determine output path
        if output_file_path is None:
            # Use same directory as JSON file, with .docx extension
            json_path = Path(json_file_path)
            output_file_path = json_path.parent / f"{json_path.stem}.docx"
        
        # Generate Word document
        result_path = export_review_to_word(review_data, str(output_file_path))
        
        print(f"✅ Word report generated: {result_path}")
        return result_path
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root directory")
        return None
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        return None
    except Exception as e:
        print(f"❌ Error generating Word report: {e}")
        return None

def main():
    """Main function."""
    if len(sys.argv) > 3:
        print("Usage: python scripts/generate_word_report.py [json_file] [output_file]")
        sys.exit(1)
    
    # Get JSON file path
    if len(sys.argv) >= 2:
        json_file_path = sys.argv[1]
    else:
        # Find latest JSON file
        json_file_path = find_latest_json_file()
        if json_file_path is None:
            sys.exit(1)
        print(f"📄 Using latest JSON file: {json_file_path}")
    
    # Get output file path
    output_file_path = sys.argv[2] if len(sys.argv) >= 3 else None
    
    # Generate Word report
    result = generate_word_report(json_file_path, output_file_path)
    if result is None:
        sys.exit(1)

if __name__ == "__main__":
    main()
