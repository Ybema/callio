#!/usr/bin/env python3
"""
project framework - Phase B Runner
==================================

Phase B: Work Packages Analysis

This script runs Phase B of the project framework, which analyzes individual 
work packages against the Logic Framework and funding call requirements.

Usage:
    python run_phase_b.py [--mode python|llm] [--funding-type horizon_eu]
"""

import sys
import argparse
import re
from pathlib import Path

# Add the framework to the Python path
framework_root = Path(__file__).parent
sys.path.insert(0, str(framework_root))

from scripts.call_context import ensure_call_dir, load_call_config, load_env_for_call, resolve_call_dir
from scripts.framework import ProposalFramework


def _wp_sort_key(path: Path):
    """Sort WP files by numeric WP identifier when available."""
    match = re.search(r"\bWP\s*[-_ ]?(\d+)\b", path.stem, re.IGNORECASE)
    if match:
        return (0, int(match.group(1)), path.name.lower())
    return (1, 9999, path.name.lower())


def get_phase_b_documents(call_dir: Path):
    """Discover documents for Phase B by scanning input directories."""
    input_dir = call_dir / "input"
    available = {}
    missing = []

    # LFA document: first .docx in lfa_documents/
    lfa_dir = input_dir / "lfa_documents"
    if lfa_dir.exists():
        lfa_files = sorted(lfa_dir.glob("*.docx"))
        if lfa_files:
            available["lfa_document"] = lfa_files[0]
        else:
            missing.append(("lfa_document", lfa_dir))
    else:
        missing.append(("lfa_document", lfa_dir))

    # Call document: prefer pre-phase processed markdown, fall back to PDF
    call_dir = input_dir / "call_documents"
    if call_dir.exists():
        call_md = sorted(call_dir.glob("*_processed.md"))
        if call_md:
            available["call_document"] = call_md[0]
        else:
            call_pdf = sorted(call_dir.glob("*.pdf"))
            if call_pdf:
                available["call_document"] = call_pdf[0]
            else:
                missing.append(("call_document", call_dir))
    else:
        missing.append(("call_document", call_dir))

    # Work packages: all .docx in work_packages/, auto-numbered by sort order
    wp_dir = input_dir / "work_packages"
    if wp_dir.exists():
        wp_files = sorted(wp_dir.glob("*.docx"), key=_wp_sort_key)
        for i, wp_file in enumerate(wp_files, 1):
            available[f"wp{i}_document"] = wp_file
        if not wp_files:
            missing.append(("work_packages", wp_dir))
    else:
        missing.append(("work_packages", wp_dir))

    return available, missing


def run_phase_b(framework_root: Path, call_dir: Path, funding_type="horizon_eu", review_mode="python"):
    """Run Phase B: Work Packages Analysis"""
    print("🔷 Phase B: Work Packages Analysis")
    print("=" * 45)
    
    # Initialize framework
    try:
        framework = ProposalFramework(framework_root, funding_type)
        session_id = framework.start_session(review_mode)
    except Exception as e:
        print(f"❌ Failed to initialize framework: {e}")
        return False
    
    # Get Phase B documents
    available_docs, missing_docs = get_phase_b_documents(call_dir)
    
    # Categorize documents
    reference_docs = {}
    wp_docs = {}
    
    for doc_type, doc_path in available_docs.items():
        if doc_type.startswith('wp') and doc_type.endswith('_document'):
            wp_docs[doc_type] = doc_path
        else:
            reference_docs[doc_type] = doc_path
    
    print(f"\n📄 Reference Documents:")
    for doc_type, doc_path in reference_docs.items():
        print(f"   ✅ {doc_type}: {doc_path.name}")
    
    print(f"\n📦 Work Package Documents:")
    for doc_type, doc_path in wp_docs.items():
        wp_num = doc_type.replace('wp', '').replace('_document', '')
        print(f"   ✅ WP{wp_num}: {doc_path.name}")
    
    if missing_docs:
        print(f"\n⚠️  Missing Documents:")
        for doc_type, doc_path in missing_docs:
            print(f"   - {doc_type}: {doc_path.name}")
    
    if not wp_docs:
        print("\n❌ No Work Package documents found for Phase B analysis!")
        print("   Required: At least one WP document")
        return False
    
    print(f"\n🔍 Analysis Configuration:")
    print(f"   - Funding Type: {funding_type}")
    print(f"   - Review Mode: {review_mode}")
    print(f"   - Reference Documents: {len(reference_docs)}")
    print(f"   - Work Packages: {len(wp_docs)}")
    
    try:
        print(f"\n🔷 Running Phase B Analysis...")
        results = framework.run_phase("work_packages", available_docs)
        
        print(f"\n✅ Phase B completed successfully!")
        print(f"   Session ID: {results['session_id']}")
        print(f"   Snapshot: {results['snapshot']['id']}")
        
        # Display review summary
        reviews = results['reviews']
        print(f"\n📊 Review Summary:")
        print(f"   Review Mode: {reviews['mode']}")
        print(f"   Documents Analyzed: {len(reviews['reviews'])}")
        
        # Show scores for each work package
        wp_scores = []
        for doc_type, doc_reviews in reviews['reviews'].items():
            if doc_type.startswith('wp') and doc_type.endswith('_document'):
                wp_num = doc_type.replace('wp', '').replace('_document', '')
                print(f"\n   📦 Work Package {wp_num}:")
                
                if reviews['mode'] == 'python':
                    total_score = 0
                    rule_count = 0
                    for rule_name, rule_result in doc_reviews.items():
                        score = rule_result.get('score', 0)
                        status = rule_result.get('status', 'Unknown')
                        print(f"     - {rule_name.replace('_', ' ').title()}: {score}% ({status})")
                        if status == 'completed':
                            total_score += score
                            rule_count += 1
                    
                    if rule_count > 0:
                        avg_score = total_score / rule_count
                        wp_scores.append(avg_score)
                        print(f"     📊 WP{wp_num} Score: {avg_score:.1f}%")
                else:  # LLM mode
                    score = doc_reviews.get('score', 0)
                    wp_scores.append(score)
                    print(f"     - LLM Analysis Score: {score}%")
        
        # Overall project score
        if wp_scores:
            overall_score = sum(wp_scores) / len(wp_scores)
            print(f"\n🎯 Overall Work Packages Score: {overall_score:.1f}%")
        
        # Show output files
        print(f"\n📝 Generated Outputs:")
        for output_type, output_data in results['outputs'].items():
            if 'file_path' in output_data:
                file_path = Path(output_data['file_path'])
                print(f"   - {output_type.upper()}: {file_path.name}")
                if output_type == 'markdown':
                    print(f"     📍 Location: {file_path}")
        
        print(f"\n🎯 Phase B Analysis Complete!")
        print(f"   Next Step: Review the work package assessments, then run Phase C")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase B failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Command line interface for Phase B"""
    parser = argparse.ArgumentParser(
        description="project framework Phase B: Work Packages Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_phase_b.py --call my-call                    # Run with default settings
  python run_phase_b.py --mode llm         # Use LLM review mode
  python run_phase_b.py --funding-type skattefunn  # Use different funding type
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
        "--mode", 
        choices=["python", "llm"], 
        default="python",
        help="Review mode: python (rules-based) or llm (contextual analysis)"
    )
    
    parser.add_argument(
        "--funding-type",
        default="horizon_eu",
        help="Funding type configuration to use (default: horizon_eu)"
    )
    
    parser.add_argument(
        "--list-documents",
        action="store_true",
        help="List available documents and exit"
    )
    
    args = parser.parse_args()

    call_dir = resolve_call_dir(args.framework_root, args.call)
    try:
        ensure_call_dir(call_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    load_env_for_call(call_dir, args.framework_root)

    try:
        call_config = load_call_config(call_dir)
        if args.funding_type == "horizon_eu":
            args.funding_type = call_config.get("funding_type", args.funding_type)
    except FileNotFoundError:
        pass
    
    if args.list_documents:
        print("📄 Available Documents for Phase B:")
        available_docs, missing_docs = get_phase_b_documents(call_dir)
        
        reference_docs = {}
        wp_docs = {}
        
        for doc_type, doc_path in available_docs.items():
            if doc_type.startswith('wp') and doc_type.endswith('_document'):
                wp_docs[doc_type] = doc_path
            else:
                reference_docs[doc_type] = doc_path
        
        print("\n📄 Reference Documents:")
        for doc_type, doc_path in reference_docs.items():
            print(f"   ✅ {doc_type}: {doc_path}")
        
        print("\n📦 Work Package Documents:")
        for doc_type, doc_path in wp_docs.items():
            print(f"   ✅ {doc_type}: {doc_path}")
        
        if missing_docs:
            print(f"\n⚠️  Missing Documents:")
            for doc_type, doc_path in missing_docs:
                print(f"   - {doc_type}: {doc_path}")
        
        return
    
    # Run Phase B
    success = run_phase_b(args.framework_root, call_dir, args.funding_type, args.mode)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
