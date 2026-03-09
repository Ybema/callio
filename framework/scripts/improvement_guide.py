#!/usr/bin/env python3
"""Generate a section-oriented improvement guide from structural + alignment reviews.

Takes the two review JSONs and the structured LFA, then reorganizes all findings
by LFA section (top-down) so the moderator can work through improvements one
section at a time with all relevant feedback in one place.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("improvement-guide")

LFA_SECTIONS = [
    "Background",
    "Overall Goal",
    "Project Purpose",
    "Project Outcomes",
    "Expected Outputs / Results",
    "Activities and Required Inputs",
]

_SECTION_PATTERNS: Dict[str, List[str]] = {
    "Background": [
        r"background",
        r"problem\b",
        r"problem origin",
        r"problem summary",
        r"current methods",
        r"limitations",
        r"proposed solution",
    ],
    "Overall Goal": [
        r"overall goal",
        r"\bgoal\b(?!.*purpose)",
    ],
    "Project Purpose": [
        r"project purpose",
        r"\bpurpose\b",
        r"\bmvp\b",
    ],
    "Project Outcomes": [
        r"outcome\s*[12]",
        r"outcomes?\b",
    ],
    "Expected Outputs / Results": [
        r"expected output",
        r"output\s*[1-7]",
        r"expected result",
        r"outputs? section",
        r"results? section",
    ],
    "Activities and Required Inputs": [
        r"activit",
        r"required inputs",
        r"timeline",
        r"implementation",
        r"milestone",
        r"budget",
        r"resource",
    ],
}

CRITERIA_LABELS = {
    "LC1": "Logical Flow",
    "LC2": "Measurable Outcomes",
    "LC3": "Activity-Outcome Linkage",
    "LC4": "Implementation Feasibility",
    "CQ1": "Clarity & Specificity",
    "CQ2": "Actionable Content",
    "CQ3": "Professional Presentation",
    "CA1": "Objectives Alignment",
    "CA2": "Scope Fit",
    "CA3": "Outcomes/Impacts Alignment",
    "CA4": "Evaluation Coverage",
    "CA5": "LFA-Call Alignment Completeness",
    "CA6": "Terminology Alignment",
}

REVIEW_LABELS = {
    "structural": "Structural",
    "alignment": "Alignment",
}


def _match_sections(text: str) -> List[str]:
    """Return LFA section names that the text references."""
    lower = text.lower()
    matched = []
    for section, patterns in _SECTION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower):
                matched.append(section)
                break
    return matched


def _finding_text_blob(finding: Dict[str, Any]) -> str:
    """Concatenate all text fields of a finding for section matching."""
    parts = []
    for key in ("gaps", "fixes", "suggested_text"):
        items = finding.get(key) or []
        parts.extend(items)
    return " ".join(parts)


def _format_finding_block(
    code: str,
    review_type: str,
    finding: Dict[str, Any],
    score: Optional[float],
) -> str:
    label = CRITERIA_LABELS.get(code, code)
    review_label = REVIEW_LABELS.get(review_type, review_type)
    score_str = f" ({score}/5)" if score is not None else ""

    lines = [f"### [{review_label}] {code}: {label}{score_str}", ""]

    gaps = finding.get("gaps") or []
    fixes = finding.get("fixes") or []
    suggested = finding.get("suggested_text") or []

    if gaps:
        lines.append("**Gap:**")
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    if fixes:
        lines.append("**Recommended fix:**")
        for f in fixes:
            lines.append(f"- {f}")
        lines.append("")

    if suggested:
        lines.append("**Suggested text:**")
        for s in suggested:
            lines.append(f"> {s}")
            lines.append("")

    return "\n".join(lines)


def _collect_scores(review_json: Dict[str, Any]) -> Dict[str, float]:
    """Return {code: score} from review JSON scores block."""
    out: Dict[str, float] = {}
    for group_key, group_val in review_json.get("scores", {}).items():
        if not isinstance(group_val, dict):
            continue
        for k, v in group_val.items():
            if isinstance(v, (int, float)) and k not in ("weight", "subtotal"):
                out[k] = float(v)
    return out


# ---------------------------------------------------------------------------
# LFA markdown section parser
# ---------------------------------------------------------------------------

_LFA_HEADER_MAP: Dict[str, str] = {
    "background": "Background",
    "overall goal": "Overall Goal",
    "project purpose": "Project Purpose",
    "project outcomes": "Project Outcomes",
    "expected outputs / results": "Expected Outputs / Results",
    "expected outputs/results": "Expected Outputs / Results",
    "expected outputs": "Expected Outputs / Results",
    "activities and required inputs": "Activities and Required Inputs",
    "activities": "Activities and Required Inputs",
    "project approach": "Expected Outputs / Results",
}


def _parse_lfa_sections(lfa_text: str) -> Dict[str, str]:
    """Split structured LFA markdown into a dict keyed by canonical section name.

    Splits on ``## `` headers.  Sub-headers (``###``) are kept inside their
    parent section.  The header line itself is excluded from the content so
    the guide can render its own heading.
    """
    sections: Dict[str, str] = {}
    current_key: Optional[str] = None
    current_lines: List[str] = []

    for line in lfa_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            header_text = stripped.lstrip("#").strip().lower()
            current_key = _LFA_HEADER_MAP.get(header_text)
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def generate_improvement_guide(
    structural_json_path: Optional[Path],
    alignment_json_path: Optional[Path],
    lfa_md_path: Optional[Path],
    output_path: Path,
    project_name: str = "Project",
) -> Dict[str, Any]:
    """Generate the section-oriented improvement guide markdown.

    Returns metadata dict with output path and stats.
    """
    reviews: List[Tuple[str, Dict[str, Any]]] = []
    for label, path in [("structural", structural_json_path), ("alignment", alignment_json_path)]:
        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                reviews.append((label, data))
            except Exception as exc:
                log.warning("Could not parse %s: %s", path, exc)

    if not reviews:
        log.warning("No review JSONs found; cannot generate improvement guide.")
        return {"ok": False, "error": "no review data"}

    lfa_sections: Dict[str, str] = {}
    if lfa_md_path and lfa_md_path.exists():
        lfa_text = lfa_md_path.read_text(encoding="utf-8", errors="ignore")
        lfa_sections = _parse_lfa_sections(lfa_text)
        log.info("Parsed %d LFA sections from %s", len(lfa_sections), lfa_md_path.name)

    all_scores: Dict[str, float] = {}
    section_blocks: Dict[str, List[str]] = {s: [] for s in LFA_SECTIONS}
    cross_cutting: List[str] = []
    finding_count = 0

    for review_type, review_data in reviews:
        scores = _collect_scores(review_data)
        all_scores.update(scores)
        findings = review_data.get("findings", {})
        for code, finding in findings.items():
            blob = _finding_text_blob(finding)
            matched = _match_sections(blob)
            block = _format_finding_block(code, review_type, finding, scores.get(code))
            finding_count += 1
            if not matched:
                cross_cutting.append(block)
            else:
                for section in matched:
                    section_blocks[section].append(block)

    structural_total = None
    structural_band = None
    alignment_total = None
    alignment_band = None
    for review_type, review_data in reviews:
        s = review_data.get("scores", {})
        if review_type == "structural":
            structural_total = s.get("total")
            structural_band = s.get("band")
        elif review_type == "alignment":
            alignment_total = s.get("total")
            alignment_band = s.get("band")

    lines: List[str] = []
    lines.append(f"# Improvement Guide: {project_name}")
    lines.append("")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    lines.append("")
    lines.append("Work through this guide top-down, one LFA section at a time.")
    lines.append("Each section shows the current LFA content followed by all review feedback.")
    lines.append("")

    lines.append("## Score Summary")
    lines.append("")
    if structural_total is not None:
        lines.append(f"- **Structural quality**: {structural_total}/5 ({structural_band})")
    if alignment_total is not None:
        lines.append(f"- **Call alignment**: {alignment_total}/5 ({alignment_band})")
    lines.append("")

    low_scores = sorted(
        [(code, sc) for code, sc in all_scores.items() if sc <= 3.0],
        key=lambda x: x[1],
    )
    if low_scores:
        lines.append("**Priority areas (score 3.0 or below):**")
        for code, sc in low_scores:
            label = CRITERIA_LABELS.get(code, code)
            lines.append(f"- {code} {label}: {sc}/5")
        lines.append("")

    lines.append("---")
    lines.append("")

    for section in LFA_SECTIONS:
        blocks = section_blocks[section]
        lines.append(f"## {section}")
        lines.append("")

        lfa_content = lfa_sections.get(section, "").strip()
        if lfa_content:
            lines.append("### Current LFA content")
            lines.append("")
            lines.append(lfa_content)
            lines.append("")
        else:
            lines.append("_No LFA content found for this section._")
            lines.append("")

        if not blocks:
            lines.append("_No specific findings for this section._")
            lines.append("")
        else:
            lines.append("### Feedback")
            lines.append("")
            for block in blocks:
                lines.append(block)
        lines.append("---")
        lines.append("")

    if cross_cutting:
        lines.append("## Cross-cutting")
        lines.append("")
        for block in cross_cutting:
            lines.append(block)
        lines.append("---")
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    log.info("Improvement guide written: %s (%d chars, %d findings)", output_path, len(content), finding_count)

    return {
        "ok": True,
        "output_path": str(output_path),
        "chars": len(content),
        "finding_count": finding_count,
        "sections_with_findings": sum(1 for s in LFA_SECTIONS if section_blocks[s]),
        "cross_cutting_count": len(cross_cutting),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate section-oriented improvement guide from Phase A reviews.")
    parser.add_argument("--structural", type=Path, help="Path to structural review JSON")
    parser.add_argument("--alignment", type=Path, help="Path to alignment review JSON")
    parser.add_argument("--lfa", type=Path, help="Path to structured LFA markdown (for reference)")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output path for improvement_guide.md")
    parser.add_argument("--project-name", default="Project", help="Project name for header")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    result = generate_improvement_guide(
        structural_json_path=args.structural,
        alignment_json_path=args.alignment,
        lfa_md_path=args.lfa,
        output_path=args.output,
        project_name=args.project_name,
    )
    if result.get("ok"):
        print(f"Guide written: {result['output_path']} ({result['finding_count']} findings)")
    else:
        print(f"Failed: {result.get('error')}")


if __name__ == "__main__":
    main()
