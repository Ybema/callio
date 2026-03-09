#!/usr/bin/env python3
"""
project framework - Phase C Runner
==================================

Phase C: Full Project Plan Analysis

This script runs Phase C of the project framework, which performs a comprehensive 
analysis of the complete project proposal including LFA, work packages, and the 
main proposal document against funding call requirements.

Usage:
    python run_phase_c.py [--mode python|llm] [--funding-type horizon_eu]
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


def _normalize_call_source(path: Path) -> str:
    """
    Normalize call source name so PDF and *_processed.md variants can be compared.
    Example: `foo.pdf` and `foo_processed.md` normalize to `foo`.
    """
    stem = path.stem
    if stem.endswith("_processed"):
        stem = stem[:-10]
    return stem.lower()


def get_phase_c_documents(call_dir: Path):
    """Discover documents for Phase C by scanning input directories."""
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

    # Strategy documents: all PDFs and Word docs in strategy_documents/
    strategy_dir = input_dir / "strategy_documents"
    if strategy_dir.exists():
        strategy_files = sorted(
            f for f in strategy_dir.iterdir()
            if f.is_file() and f.suffix.lower() in ['.pdf', '.docx', '.doc']
        )
        for i, sf in enumerate(strategy_files, 1):
            key = "strategy_document" if i == 1 else f"strategy_document_{i}"
            available[key] = sf

    # Guidance documents: additional PDFs in call_documents/ beyond the main call
    if call_dir.exists():
        guidance_pdfs = sorted(call_dir.glob("*.pdf"))
        call_doc = available.get("call_document")
        call_source = _normalize_call_source(call_doc) if call_doc else ""
        for gf in guidance_pdfs:
            if call_doc and gf.resolve() == call_doc.resolve():
                continue
            if call_source and _normalize_call_source(gf) == call_source:
                continue
            available["guidance_document"] = gf
            break

    return available, missing


def run_phase_c(framework_root: Path, call_dir: Path, funding_type="horizon_eu", review_mode="python"):
    """Run Phase C: Full Project Plan Analysis"""
    print("🔷 Phase C: Full Project Plan Analysis")
    print("=" * 50)
    
    # Initialize framework
    try:
        framework = ProposalFramework(framework_root, funding_type)
        session_id = framework.start_session(review_mode)
    except Exception as e:
        print(f"❌ Failed to initialize framework: {e}")
        return False
    
    # Get Phase C documents
    available_docs, missing_docs = get_phase_c_documents(call_dir)
    
    # Categorize documents
    core_docs = {}
    wp_docs = {}
    support_docs = {}
    
    for doc_type, doc_path in available_docs.items():
        if doc_type.startswith('wp') and doc_type.endswith('_document'):
            wp_docs[doc_type] = doc_path
        elif doc_type in ['lfa_document', 'call_document', 'part_b_document']:
            core_docs[doc_type] = doc_path
        else:
            support_docs[doc_type] = doc_path
    
    print(f"\n📄 Core Proposal Documents:")
    for doc_type, doc_path in core_docs.items():
        print(f"   ✅ {doc_type.replace('_', ' ').title()}: {doc_path.name}")
    
    print(f"\n📦 Work Package Documents:")
    for doc_type, doc_path in wp_docs.items():
        wp_num = doc_type.replace('wp', '').replace('_document', '')
        print(f"   ✅ WP{wp_num}: {doc_path.name}")
    
    if support_docs:
        print(f"\n📋 Supporting Documents:")
        for doc_type, doc_path in support_docs.items():
            print(f"   ✅ {doc_type.replace('_', ' ').title()}: {doc_path.name}")
    
    if missing_docs:
        print(f"\n⚠️  Missing Optional Documents:")
        for doc_type, doc_path in missing_docs:
            if not doc_type.startswith('part_b_alt'):  # Don't show Part B alternatives
                print(f"   - {doc_type}: {doc_path.name}")
    
    if not core_docs:
        print("\n❌ No core documents found for Phase C analysis!")
        print("   Required: LFA document, call document, or Part B document")
        return False
    
    print(f"\n🔍 Analysis Configuration:")
    print(f"   - Funding Type: {funding_type}")
    print(f"   - Review Mode: {review_mode}")
    print(f"   - Core Documents: {len(core_docs)}")
    print(f"   - Work Packages: {len(wp_docs)}")
    print(f"   - Supporting Documents: {len(support_docs)}")
    
    try:
        print(f"\n🔷 Running Phase C Analysis...")
        results = framework.run_phase("full_plan", available_docs)
        
        print(f"\n✅ Phase C completed successfully!")
        print(f"   Session ID: {results['session_id']}")
        print(f"   Snapshot: {results['snapshot']['id']}")
        
        # Display review summary
        reviews = results['reviews']
        print(f"\n📊 Comprehensive Review Summary:")
        print(f"   Review Mode: {reviews['mode']}")
        print(f"   Total Documents Analyzed: {len(reviews['reviews'])}")
        
        # Show scores by category
        core_scores = []
        wp_scores = []
        support_scores = []
        
        for doc_type, doc_reviews in reviews['reviews'].items():
            doc_score = None
            
            if reviews['mode'] == 'python':
                total_score = 0
                rule_count = 0
                for rule_name, rule_result in doc_reviews.items():
                    score = rule_result.get('score', 0)
                    status = rule_result.get('status', 'Unknown')
                    if status == 'completed':
                        total_score += score
                        rule_count += 1
                
                if rule_count > 0:
                    doc_score = total_score / rule_count
            else:  # LLM mode
                doc_score = doc_reviews.get('score', 0)
            
            # Categorize the score
            if doc_type in ['lfa_document', 'call_document', 'part_b_document']:
                if doc_score is not None:
                    core_scores.append(doc_score)
                print(f"\n   📄 {doc_type.replace('_', ' ').title()}: {doc_score:.1f}%" if doc_score else f"\n   📄 {doc_type.replace('_', ' ').title()}: No score")
            elif doc_type.startswith('wp') and doc_type.endswith('_document'):
                if doc_score is not None:
                    wp_scores.append(doc_score)
                wp_num = doc_type.replace('wp', '').replace('_document', '')
                print(f"\n   📦 Work Package {wp_num}: {doc_score:.1f}%" if doc_score else f"\n   📦 Work Package {wp_num}: No score")
            else:
                if doc_score is not None:
                    support_scores.append(doc_score)
                print(f"\n   📋 {doc_type.replace('_', ' ').title()}: {doc_score:.1f}%" if doc_score else f"\n   📋 {doc_type.replace('_', ' ').title()}: No score")
        
        # Calculate category averages
        print(f"\n🎯 Category Scores:")
        if core_scores:
            core_avg = sum(core_scores) / len(core_scores)
            print(f"   📄 Core Documents: {core_avg:.1f}% (avg of {len(core_scores)} docs)")
        
        if wp_scores:
            wp_avg = sum(wp_scores) / len(wp_scores)
            print(f"   📦 Work Packages: {wp_avg:.1f}% (avg of {len(wp_scores)} WPs)")
        
        if support_scores:
            support_avg = sum(support_scores) / len(support_scores)
            print(f"   📋 Supporting Documents: {support_avg:.1f}% (avg of {len(support_scores)} docs)")
        
        # Overall project score
        all_scores = core_scores + wp_scores + support_scores
        if all_scores:
            overall_score = sum(all_scores) / len(all_scores)
            print(f"\n🏆 Overall Project Score: {overall_score:.1f}%")
            
            # Score interpretation
            if overall_score >= 80:
                print("   🌟 Excellent - Strong proposal ready for submission")
            elif overall_score >= 70:
                print("   ✅ Good - Minor improvements recommended")
            elif overall_score >= 60:
                print("   ⚠️  Fair - Significant improvements needed")
            else:
                print("   ❌ Poor - Major revisions required")
        
        # Show output files
        print(f"\n📝 Generated Outputs:")
        for output_type, output_data in results['outputs'].items():
            if 'file_path' in output_data:
                file_path = Path(output_data['file_path'])
                print(f"   - {output_type.upper()}: {file_path.name}")
                if output_type == 'markdown':
                    print(f"     📍 Location: {file_path}")
        
        print(f"\n🎯 Phase C Analysis Complete!")
        print(f"   🔍 Review the comprehensive analysis report")
        print(f"   📊 Use the scores to prioritize improvements")
        print(f"   📋 Address any flagged issues before submission")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase C failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Command line interface for Phase C"""
    parser = argparse.ArgumentParser(
        description="project framework Phase C: Full Project Plan Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_phase_c.py --call my-call                    # Run with default settings
  python run_phase_c.py --mode llm         # Use LLM review mode
  python run_phase_c.py --funding-type skattefunn  # Use different funding type
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
        print("📄 Available Documents for Phase C:")
        available_docs, missing_docs = get_phase_c_documents(call_dir)
        
        # Categorize for display
        core_docs = {}
        wp_docs = {}
        support_docs = {}
        
        for doc_type, doc_path in available_docs.items():
            if doc_type.startswith('wp') and doc_type.endswith('_document'):
                wp_docs[doc_type] = doc_path
            elif doc_type in ['lfa_document', 'call_document', 'part_b_document']:
                core_docs[doc_type] = doc_path
            else:
                support_docs[doc_type] = doc_path
        
        print("\n📄 Core Documents:")
        for doc_type, doc_path in core_docs.items():
            print(f"   ✅ {doc_type}: {doc_path}")
        
        print("\n📦 Work Package Documents:")
        for doc_type, doc_path in wp_docs.items():
            print(f"   ✅ {doc_type}: {doc_path}")
        
        if support_docs:
            print("\n📋 Supporting Documents:")
            for doc_type, doc_path in support_docs.items():
                print(f"   ✅ {doc_type}: {doc_path}")
        
        if missing_docs:
            print(f"\n⚠️  Missing Optional Documents:")
            for doc_type, doc_path in missing_docs:
                if not doc_type.startswith('part_b_alt'):
                    print(f"   - {doc_type}: {doc_path}")
        
        return
    
    # Run Phase C
    success = run_phase_c(args.framework_root, call_dir, args.funding_type, args.mode)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
