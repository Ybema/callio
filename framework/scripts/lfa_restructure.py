#!/usr/bin/env python3
"""
LFA Document Restructuring Module

Takes a raw LFA DOCX-converted markdown and produces:
1. lfa_structured.md  — strict LFA template populated from source content
2. lfa_derivation.md  — strategic reasoning, analysis, and context that
                        doesn't fit into LFA cells but is valuable for proposals

Two-pass LLM architecture using Anthropic Claude.
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("lfa-restructure")


def setup_logging(verbose: bool = False):
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)


# ---------------------------------------------------------------------------
# LLM helper (Anthropic streaming)
# ---------------------------------------------------------------------------

def call_anthropic(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> Dict[str, Any]:
    """Call Anthropic with streaming to avoid HTTP timeout on large inputs."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        text_parts = []
        inp_tokens = 0
        out_tokens = 0
        with client.messages.stream(
            model=model,
            max_tokens=32000,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.0,
        ) as stream:
            for chunk in stream.text_stream:
                text_parts.append(chunk)
            resp = stream.get_final_message()
            inp_tokens = getattr(resp.usage, "input_tokens", 0)
            out_tokens = getattr(resp.usage, "output_tokens", 0)
        return {"ok": True, "text": "".join(text_parts).strip(), "tokens": inp_tokens + out_tokens}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

STRUCTURED_SYSTEM = """\
You are an expert in Logical Framework Approach (LFA) methodology.

Your task: extract and organize content from a source document into a STRICT LFA template.

The LFA hierarchy (each level must have Indicator + Verification where applicable):

## Background
- Problem origin
- Current methods/approaches to solve the problem
- Limitations of current approaches
- Proposed solution and its advantages

## Overall Goal
The ultimate broad change the project contributes to (aspirational, not directly measurable by the project).
- State who benefits
- Provide Indicator and Verification means

## Project Purpose
ONE purpose — the specific measurable change when beneficiaries adopt/use project results.
- Must align with the problem statement
- Provide Indicator and Verification means

## Project Outcomes
Success factors — behavioral/condition changes indicating progress.
- Begin with verbs (increase, expand, improve, reduce, establish)
- Specific and measurable
- NOT activities or processes
- Each with Indicator and Verification means

## Expected Outputs / Results
Concrete deliverables the project guarantees.
- SMART criteria (Specific, Measurable, Achievable, Relevant, Time-bound)
- Stated as achieved status ("Having established...", "Having delivered...")
- Each linked to an Outcome
- Each with Indicator and Verification means

## Activities and Required Inputs
Tasks to achieve/sustain results.
- Each linked to a Result
- Include: What, Where, Budget element, Activity costs where available
- Methodology, timeline, innovative approaches

CRITICAL RULES:
- Extract ONLY from the source document — NEVER invent content
- If a section has no content in the source, write: "[NOT PROVIDED IN SOURCE — needs input]"
- Preserve specific numbers, names, dates, and technical details exactly
- Use markdown tables for Indicator/Verification columns
- If the source has content that maps to an LFA level but isn't perfectly formatted, \
restructure it to fit while preserving all substance
"""

DERIVATION_SYSTEM = """\
You are an expert in proposal strategy and Logical Framework methodology.

Your task: extract ALL strategic reasoning, analysis, and contextual content from a source \
document that does NOT belong in the formal LFA template cells but IS valuable for \
proposal writing.

This includes:
- Problem analysis / bottleneck identification and mapping
- Theory of change / contribution logic / causal chains
- How identified problems/gaps map to chosen outcomes (with justification)
- Call requirements ↔ proposal alignment mapping / comparison tables
- Technical approach rationale and methodology justification
- Market and competitive context
- Stakeholder analysis
- Risk considerations and mitigation
- Consortium logic and partner roles
- Any reasoning about WHY specific choices were made

Output structure:
- Use markdown headings to organize by topic
- Preserve tables, mappings, and comparison matrices exactly
- Keep all specific details (names, numbers, references)
- If the source document contains NO derivation logic (just a filled-in template), \
state that clearly and list what strategic analysis might be needed

CRITICAL RULES:
- Extract ONLY from the source document — NEVER invent content
- Do NOT duplicate content that belongs in the LFA structured template
- Preserve the reasoning chain — the logic of HOW the project got from problem → outcomes
"""


# ---------------------------------------------------------------------------
# Core restructuring
# ---------------------------------------------------------------------------

def restructure_lfa(
    source_markdown: str,
    call_context_path: Optional[Path] = None,
    instructions_path: Optional[Path] = None,
    template_path: Optional[Path] = None,
    output_dir: Path = Path("."),
    model: str = "claude-sonnet-4-20250514",
) -> Dict[str, Any]:
    """
    Restructure an LFA source document into structured template + derivation logic.

    Returns dict with paths and metadata.
    """
    t0 = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load optional context
    call_context = ""
    if call_context_path and call_context_path.exists():
        call_context = call_context_path.read_text(encoding="utf-8", errors="ignore")
        log.info(f"Loaded call context: {len(call_context):,} chars")

    instructions = ""
    if instructions_path and instructions_path.exists():
        instructions = instructions_path.read_text(encoding="utf-8", errors="ignore")
        log.info(f"Loaded instructions: {len(instructions):,} chars")

    template = ""
    if template_path and template_path.exists():
        template = template_path.read_text(encoding="utf-8", errors="ignore")
        log.info(f"Loaded LFA template: {len(template):,} chars")

    # Build context blocks — structured pass gets ONLY template, derivation pass gets everything
    template_block = ""
    if template:
        template_block = f"\n\n--- LFA TEMPLATE STRUCTURE (follow this structure) ---\n{template}\n"

    derivation_context_block = template_block
    if call_context:
        derivation_context_block += f"\n\n--- CALL CONTEXT (use to identify what analysis is missing) ---\n{call_context[:30000]}\n"
    if instructions:
        derivation_context_block += f"\n\n--- CALL INSTRUCTIONS (use to identify what guidance exists) ---\n{instructions[:15000]}\n"

    total_tokens = 0

    # --- Pass 1: Structured LFA ---
    log.info("Pass 1: Extracting structured LFA content...")
    user_structured = (
        f"Source LFA document:\n\n{source_markdown[:80000]}"
        f"{template_block}\n\n"
        "Extract and organize ONLY content that exists in the source LFA document into "
        "the strict LFA template structure. Follow the template sections exactly. "
        "Use markdown tables for Indicator/Verification. "
        "If a section has no content in the source document, write '[NOT PROVIDED IN SOURCE — needs input]'. "
        "Do NOT generate, infer, or synthesize content from any other source."
    )
    r1 = call_anthropic(STRUCTURED_SYSTEM, user_structured, model)
    if not r1["ok"]:
        log.error(f"Pass 1 failed: {r1.get('error')}")
        return {"ok": False, "error": f"structured pass failed: {r1.get('error')}"}

    total_tokens += r1.get("tokens", 0)
    structured_path = output_dir / "lfa_structured.md"
    structured_header = (
        f"# LFA Structured Framework\n\n"
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"
        f"_Model: `{model}`_\n\n"
    )
    structured_content = structured_header + r1["text"] + "\n"
    structured_path.write_text(structured_content, encoding="utf-8")
    log.info(f"  Written: {structured_path} ({len(structured_content):,} chars, {r1.get('tokens', 0):,} tokens)")

    # --- Pass 2: Derivation logic ---
    log.info("Pass 2: Extracting derivation logic and strategic context...")
    user_derivation = (
        f"Source LFA document:\n\n{source_markdown[:80000]}"
        f"{derivation_context_block}\n\n"
        "Extract all strategic reasoning, analysis, and context from the SOURCE DOCUMENT that "
        "does NOT belong in the formal LFA cells but is valuable for proposal writing. "
        "If the source lacks derivation logic, use the call context to identify what "
        "strategic analysis is missing and should be developed."
    )
    r2 = call_anthropic(DERIVATION_SYSTEM, user_derivation, model)
    if not r2["ok"]:
        log.error(f"Pass 2 failed: {r2.get('error')}")
        return {"ok": False, "error": f"derivation pass failed: {r2.get('error')}"}

    total_tokens += r2.get("tokens", 0)
    derivation_path = output_dir / "lfa_derivation.md"
    derivation_header = (
        f"# LFA Derivation Logic & Strategic Context\n\n"
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"
        f"_Model: `{model}`_\n\n"
    )
    derivation_content = derivation_header + r2["text"] + "\n"
    derivation_path.write_text(derivation_content, encoding="utf-8")
    log.info(f"  Written: {derivation_path} ({len(derivation_content):,} chars, {r2.get('tokens', 0):,} tokens)")

    elapsed = time.time() - t0
    meta = {
        "ok": True,
        "structured_path": str(structured_path),
        "derivation_path": str(derivation_path),
        "structured_chars": len(structured_content),
        "derivation_chars": len(derivation_content),
        "total_tokens": total_tokens,
        "elapsed_seconds": round(elapsed, 1),
        "model": model,
    }
    log.info(f"Done in {elapsed:.1f}s — {total_tokens:,} tokens total")
    return meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Restructure LFA document into structured template + derivation logic.",
    )
    parser.add_argument("--source", "-s", type=Path, required=True,
                        help="Path to raw LFA markdown (converted from DOCX)")
    parser.add_argument("--call-context", type=Path, default=None,
                        help="Path to pre-phase summary.md")
    parser.add_argument("--instructions", type=Path, default=None,
                        help="Path to pre-phase instructions.md")
    parser.add_argument("--template", type=Path, default=None,
                        help="Path to LFA template markdown")
    parser.add_argument("--output-dir", type=Path, default=Path("."),
                        help="Output directory for lfa_structured.md and lfa_derivation.md")
    parser.add_argument("--model", default="claude-sonnet-4-20250514",
                        help="Anthropic model (default: claude-sonnet-4-20250514)")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: {args.source} not found")
        sys.exit(1)

    # Load .env if present
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)

    setup_logging(verbose=args.verbose)
    source_md = args.source.read_text(encoding="utf-8", errors="ignore")
    log.info(f"Source document: {args.source} ({len(source_md):,} chars)")

    result = restructure_lfa(
        source_markdown=source_md,
        call_context_path=args.call_context,
        instructions_path=args.instructions,
        template_path=args.template,
        output_dir=args.output_dir,
        model=args.model,
    )

    if not result.get("ok"):
        print(f"Failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
