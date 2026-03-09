#!/usr/bin/env python3
"""
Simple evaluator that accepts JSON input and returns JSON scores using the review engine.
"""
import json
import sys
import os
from pathlib import Path

# Add the scripts directory to the path so we can import the review engine
scripts_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_dir))

try:
    from review_engine.review_engine import run_llm_criteria, _load_prompt
except ImportError:
    print("Error: Could not import review engine. Make sure you're in the correct directory.", file=sys.stderr)
    sys.exit(1)

def evaluate_criteria(input_data):
    """
    Evaluate criteria based on JSON input.
    
    Args:
        input_data: Dict with keys: criteria, call_outline, lfa_outline, call_excerpts, lfa_excerpts
    
    Returns:
        JSON response with scores and evidence for each criterion
    """
    
    # Load the call alignment prompt
    prompt_file = scripts_dir / "review_engine" / "prompts" / "call_alignment.txt"
    if not prompt_file.exists():
        return {"error": "Call alignment prompt file not found"}
    
    system_prompt = prompt_file.read_text(encoding="utf-8")
    
    # Prepare the payload for the LLM
    payload = {
        "criteria": input_data.get("criteria", []),
        "call_outline": input_data.get("call_outline", []),
        "lfa_outline": input_data.get("lfa_outline", []),
        "call_excerpts": input_data.get("call_excerpts", ""),
        "lfa_excerpts": input_data.get("lfa_excerpts", "")
    }
    
    # Use a lightweight model for testing
    model = "gpt-4o-mini"
    
    try:
        # Call the LLM criteria evaluation
        result = run_llm_criteria(model, system_prompt, payload, temperature=0.0)
        
        # Remove internal fields from the response
        clean_result = {}
        for key, value in result.items():
            if not key.startswith("_"):
                clean_result[key] = value
        
        return clean_result
        
    except Exception as e:
        return {"error": f"Evaluation failed: {str(e)}"}

def main():
    """Main function to handle JSON input and return JSON output."""
    try:
        # Read JSON input from stdin or command line argument
        if len(sys.argv) > 1:
            input_text = sys.argv[1]
        else:
            input_text = sys.stdin.read()
        
        # Parse JSON input
        try:
            input_data = json.loads(input_text)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON input: {str(e)}"}
        
        # Validate required fields
        required_fields = ["criteria", "call_outline", "lfa_outline", "call_excerpts", "lfa_excerpts"]
        for field in required_fields:
            if field not in input_data:
                return {"error": f"Missing required field: {field}"}
        
        # Evaluate criteria
        result = evaluate_criteria(input_data)
        
        # Return JSON response
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        error_result = {"error": f"Unexpected error: {str(e)}"}
        print(json.dumps(error_result, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()