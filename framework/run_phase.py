#!/usr/bin/env python3
"""
project framework Phase Runner

Interactive script to run individual phases of the project framework.
This makes it easy to test Phase A, B, and C step-by-step.
"""

import sys
from pathlib import Path

# Add the framework to the Python path
framework_root = Path(__file__).parent
sys.path.insert(0, str(framework_root))

from core.framework import project framework


def list_available_documents():
    """List available documents for testing."""
    horizon_root = framework_root.parent
    
    documents = {
        "lfa_document": horizon_root / "input" / "uploads" / "lfa_documents" / "Project_Logical_Framework.docx",
        "call_document": horizon_root / "output" / "extracted_call_content_markdown.md", 
        "part_b_document": horizon_root / "input" / "uploads" / "main_proposals" / "Project Part B.docx",
        "wp1_document": horizon_root / "input" / "uploads" / "work_packages" / "Project - WP1.docx",
        "wp2_document": horizon_root / "input" / "uploads" / "work_packages" / "Project - WP2.docx",
        "wp3_document": horizon_root / "input" / "uploads" / "work_packages" / "Project - WP3.docx",
        "wp4_document": horizon_root / "input" / "uploads" / "work_packages" / "Project - WP4.docx",
        "wp5_document": horizon_root / "input" / "uploads" / "work_packages" / "Project - WP5.docx"
    }
    
    available = {}
    missing = {}
    
    for doc_type, doc_path in documents.items():
        if doc_path.exists():
            available[doc_type] = doc_path
        else:
            missing[doc_type] = doc_path
    
    return available, missing


def run_phase_a():
    """Run Phase A: LFA Analysis"""
    print("🔷 Phase A: LFA (Logic Framework Analysis)")
    print("=" * 50)
    
    # Initialize framework
    framework = project framework(framework_root, "horizon_eu")
    session_id = framework.start_session("python")
    
    # Get available documents
    available, missing = list_available_documents()
    
    print(f"\n📄 Available Documents:")
    for doc_type, doc_path in available.items():
        print(f"   ✅ {doc_type}: {doc_path.name}")
    
    if missing:
        print(f"\n❌ Missing Documents:")
        for doc_type, doc_path in missing.items():
            print(f"   - {doc_type}: {doc_path}")
    
    # Select documents appropriate for Phase A (LFA)
    phase_a_docs = {}
    
    # For Phase A, we typically need LFA document and call document
    if "lfa_document" in available:
        phase_a_docs["lfa_draft"] = available["lfa_document"]
    if "call_document" in available:
        phase_a_docs["call_document"] = available["call_document"]
    
    if not phase_a_docs:
        print("\n⚠️  No suitable documents found for Phase A")
        return False
    
    print(f"\n🔷 Running Phase A with {len(phase_a_docs)} documents...")
    
    try:
        # Run Phase A
        results = framework.run_phase("lfa", phase_a_docs)
        
        print(f"\n✅ Phase A completed successfully!")
        print(f"   Session ID: {results['session_id']}")
        print(f"   Snapshot: {results['snapshot']['id']}")
        print(f"   Outputs: {list(results['outputs'].keys())}")
        
        # Show output file locations
        print(f"\n📝 Generated Files:")
        for output_type, output_data in results['outputs'].items():
            if 'file_path' in output_data:
                print(f"   - {output_type.upper()}: {output_data['file_path']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase A failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_phase_b():
    """Run Phase B: Work Packages Analysis"""
    print("🔷 Phase B: Work Packages Analysis")
    print("=" * 50)
    
    # Initialize framework
    framework = project framework(framework_root, "horizon_eu")
    session_id = framework.start_session("python")
    
    # Get available documents
    available, missing = list_available_documents()
    
    # Select documents for Phase B (Work Packages)
    phase_b_docs = {}
    
    # For Phase B, we need LFA, call document, and WP documents
    if "lfa_document" in available:
        phase_b_docs["lfa_document"] = available["lfa_document"]
    if "call_document" in available:
        phase_b_docs["call_document"] = available["call_document"]
    
    # Add all available WP documents
    for doc_type, doc_path in available.items():
        if doc_type.startswith("wp") and doc_type.endswith("_document"):
            phase_b_docs[doc_type] = doc_path
    
    print(f"\n📄 Phase B Documents:")
    for doc_type, doc_path in phase_b_docs.items():
        print(f"   ✅ {doc_type}: {doc_path.name}")
    
    if not phase_b_docs:
        print("\n⚠️  No suitable documents found for Phase B")
        return False
    
    print(f"\n🔷 Running Phase B with {len(phase_b_docs)} documents...")
    
    try:
        # Run Phase B
        results = framework.run_phase("work_packages", phase_b_docs)
        
        print(f"\n✅ Phase B completed successfully!")
        print(f"   Session ID: {results['session_id']}")
        print(f"   Snapshot: {results['snapshot']['id']}")
        print(f"   Outputs: {list(results['outputs'].keys())}")
        
        # Show output file locations
        print(f"\n📝 Generated Files:")
        for output_type, output_data in results['outputs'].items():
            if 'file_path' in output_data:
                print(f"   - {output_type.upper()}: {output_data['file_path']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase B failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_phase_c():
    """Run Phase C: Full Plan Analysis"""
    print("🔷 Phase C: Full Plan Analysis")
    print("=" * 50)
    
    # Initialize framework
    framework = project framework(framework_root, "horizon_eu")
    session_id = framework.start_session("python")
    
    # Get available documents
    available, missing = list_available_documents()
    
    # Select documents for Phase C (Full Plan)
    phase_c_docs = {}
    
    # For Phase C, we need all documents including Part B
    if "lfa_document" in available:
        phase_c_docs["lfa_document"] = available["lfa_document"]
    if "call_document" in available:
        phase_c_docs["call_document"] = available["call_document"]
    if "part_b_document" in available:
        phase_c_docs["part_b_document"] = available["part_b_document"]
    
    # Add all available WP documents
    for doc_type, doc_path in available.items():
        if doc_type.startswith("wp") and doc_type.endswith("_document"):
            phase_c_docs[doc_type] = doc_path
    
    print(f"\n📄 Phase C Documents:")
    for doc_type, doc_path in phase_c_docs.items():
        print(f"   ✅ {doc_type}: {doc_path.name}")
    
    if not phase_c_docs:
        print("\n⚠️  No suitable documents found for Phase C")
        return False
    
    print(f"\n🔷 Running Phase C with {len(phase_c_docs)} documents...")
    
    try:
        # Run Phase C
        results = framework.run_phase("full_plan", phase_c_docs)
        
        print(f"\n✅ Phase C completed successfully!")
        print(f"   Session ID: {results['session_id']}")
        print(f"   Snapshot: {results['snapshot']['id']}")
        print(f"   Outputs: {list(results['outputs'].keys())}")
        
        # Show output file locations
        print(f"\n📝 Generated Files:")
        for output_type, output_data in results['outputs'].items():
            if 'file_path' in output_data:
                print(f"   - {output_type.upper()}: {output_data['file_path']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase C failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main interactive runner"""
    print("🚀 project framework Phase Runner")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python run_phase.py A    # Run Phase A (LFA)")
        print("  python run_phase.py B    # Run Phase B (Work Packages)")
        print("  python run_phase.py C    # Run Phase C (Full Plan)")
        print("  python run_phase.py all  # Run all phases in sequence")
        print("  python run_phase.py list # List available documents")
        return
    
    command = sys.argv[1].upper()
    
    if command == "LIST":
        available, missing = list_available_documents()
        print("\n📄 Available Documents:")
        for doc_type, doc_path in available.items():
            print(f"   ✅ {doc_type}: {doc_path.name}")
        if missing:
            print("\n❌ Missing Documents:")
            for doc_type, doc_path in missing.items():
                print(f"   - {doc_type}: {doc_path.name}")
    
    elif command == "A":
        run_phase_a()
    
    elif command == "B":
        run_phase_b()
    
    elif command == "C":
        run_phase_c()
    
    elif command == "ALL":
        print("🔄 Running all phases in sequence...\n")
        success = True
        
        if not run_phase_a():
            success = False
        print("\n" + "="*50 + "\n")
        
        if success and not run_phase_b():
            success = False
        print("\n" + "="*50 + "\n")
        
        if success and not run_phase_c():
            success = False
        
        if success:
            print("\n🎉 All phases completed successfully!")
        else:
            print("\n❌ Some phases failed. Check output above.")
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Use A, B, C, ALL, or LIST")


if __name__ == "__main__":
    main()
