# Review Engine

A minimal, LLM-first review engine for evaluating Logic Framework Analysis (LFA) documents against funding calls. This engine performs structured evaluation across three main dimensions:

- **Call Alignment (CA)**: How well the LFA matches the funding call requirements
- **Logic Consistency (LC)**: Internal coherence and structure of the LFA
- **Content Quality (CQ)**: Writing quality and specificity

## Features

- **Hybrid Evaluation**: Combines LLM reasoning with deterministic Python checks
- **Structured Outputs**: Returns detailed JSON with scores, evidence, gaps, and fixes
- **Configurable Criteria**: Route criteria to LLM or Python via `criteria.json`
- **Markdown Reports**: Generates human-readable review reports
- **Minimal Dependencies**: Only requires OpenAI client + optional textstat

## Quick Start

### 1. Setup Environment

```bash
cd project framework/scripts/review_engine
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set API Key

```bash
export OPENAI_API_KEY="sk-..."  # Your OpenAI API key
```

### 3. Run Review

```python
from review_engine import run_review

result = run_review(
    lfa_md_path="path/to/your/lfa.md",
    call_md_path="path/to/your/call.md",
    run_config_path="criteria.json",
    model="gpt-4o-mini",
    temperature=0.0,
    return_markdown_report=True
)

print(f"Total Score: {result['scores']['total']} / 5")
print(f"Band: {result['scores']['band']}")
```

### 4. Test with Sample Data

```bash
python test_review.py
```

## File Structure

```
review_engine/
├── review_engine.py              # Main engine implementation
├── criteria.json                 # Criteria routing configuration
├── eligibility_checklist.json    # Eligibility requirements for CA5
├── requirements.txt              # Python dependencies
├── test_review.py               # Test script with sample data
├── README.md                    # This file
└── prompts/                     # LLM prompt templates
    ├── call_alignment.txt       # CA criteria prompts
    ├── internal_consistency.txt # LC criteria prompts
    └── content_quality.txt      # CQ criteria prompts
```

## Evaluation Criteria

### Call Alignment (CA) - 30% weight
- **CA1**: Objectives alignment
- **CA2**: Scope fit
- **CA3**: Outcomes/Impacts alignment
- **CA4**: Evaluation coverage
- **CA5**: Eligibility/Formalities (Python)
- **CA6**: Terminology/definitions alignment

### Logic Consistency (LC) - 50% weight
- **LC1**: Hierarchy logic (Goal→Purpose→Outcomes→Outputs→Activities)
- **LC2**: Traceability
- **LC3**: KPI-SMART assessment
- **LC4**: Temporal completeness (Python)
- **LC5**: Risk linkage
- **LC6**: Terminology consistency
- **LC7**: Duplication detection (Python)
- **LC8**: Structural completeness

### Content Quality (CQ) - 20% weight
- **CQ1**: Readability (Python, optional)
- **CQ2**: Specificity
- **CQ3**: Writing quality
- **CQ4**: Terminology consistency

## Configuration

### Criteria Routing (`criteria.json`)

```json
{
  "criteria": {
    "CA1": "llm",
    "CA2": "llm", 
    "CA3": "llm",
    "CA4": "llm",
    "CA5": "python",
    "CA6": "llm",
    "LC1": "llm",
    "LC2": "llm",
    "LC3": "llm",
    "LC4": "python",
    "LC5": "llm",
    "LC6": "llm",
    "LC7": "python",
    "LC8": "llm",
    "CQ1": "python",
    "CQ2": "llm",
    "CQ3": "llm",
    "CQ4": "llm"
  }
}
```

### Eligibility Checklist (`eligibility_checklist.json`)

```json
{
  "hard": [
    "Minimum 3 legal entities",
    "At least 1 from Member State", 
    "At least 1 from Associated Country",
    "TRL 5-7",
    "Budget cap",
    "Duration /months"
  ],
  "soft": [
    "Gender plan",
    "Open science practices",
    "Data management plan",
    "Ethics requirements",
    "Dissemination strategy"
  ]
}
```

## Output Format

The engine returns a structured dictionary with:

```python
{
  "meta": {
    "engine_version": "0.2.0",
    "model": "gpt-4o-mini",
    "timestamp": "2024-01-01T12:00:00",
    "prompt_versions": {"CA": "v1", "LC": "v1", "CQ": "v1"},
    "paths": {...}
  },
  "scores": {
    "CA": {"CA1": 4.2, "CA2": 3.8, ...},
    "LC": {"LC1": 4.5, "LC2": 4.0, ...},
    "CQ": {"CQ1": 3.5, "CQ2": 4.1, ...},
    "total": 4.1,
    "band": "Strong"
  },
  "findings": {
    "CA1": {
      "evidence": [{"quote": "...", "loc": "..."}],
      "gaps": ["..."],
      "fixes": ["..."]
    },
    ...
  }
}
```

## Scoring Bands

- **Outstanding**: 4.5-5.0
- **Strong**: 4.0-4.4
- **Adequate**: 3.5-3.9
- **Needs Work**: 0.0-3.4

## Integration with project framework

This review engine is designed to be integrated into the project framework workflow:

1. **Phase A**: Use for initial LFA evaluation
2. **Iterative Review**: Run after each LFA revision
3. **Final Assessment**: Comprehensive review before submission

## Troubleshooting

### Common Issues

1. **OpenAI API Key**: Make sure `OPENAI_API_KEY` is set in your environment
2. **Dependencies**: Install with `pip install -r requirements.txt`
3. **File Paths**: Use absolute paths or ensure files are in the correct location
4. **JSON Parsing**: Check that input files are valid Markdown

### Error Handling

The engine includes robust error handling:
- LLM failures are logged with raw responses
- Missing files return default scores with explanatory notes
- JSON parsing errors are caught and reported

## Customization

### Adding New Criteria

1. Add criterion to `criteria.json`
2. Create prompt section in relevant prompt file
3. Update routing logic in `review_engine.py`

### Modifying Weights

Edit the weight calculation in `run_review()`:

```python
total = 0.30 * ca + 0.50 * lc + 0.20 * cq  # Adjust these weights
```

### Custom Prompts

Modify prompt files in `prompts/` directory. Keep the JSON output format consistent.

## License

Part of the project framework project for Horizon Europe proposal development.
