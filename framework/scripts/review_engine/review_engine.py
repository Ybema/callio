# review_engine.py
# Minimal, LLM-first review engine with tiny Python guardrails.
# Inputs: LFA.md, CALL.md, criteria.json; prompt files under prompts/.
# Output: dict with scores/findings (+ optional Markdown report).

from __future__ import annotations
import json, re, difflib, pathlib, datetime, os, time
from typing import Dict, List, Any, Tuple

# Optional dependency for CQ1 readability
try:
    import textstat  # pip install textstat
except Exception:
    textstat = None

# ---- LLM Provider (supports both Cursor CLI and OpenAI) ----
try:
    from .llm_provider import LLMProvider
except ImportError:
    # Fallback for when running as script
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from llm_provider import LLMProvider


# ---------------------------
# Markdown helpers (tiny)
# ---------------------------
_H_RE = re.compile(r'^(#{1,3})\s+(.+)$', re.M)

def split_markdown(md: str) -> Dict[str, str]:
    """Split by #/##/### headings to a {heading: body} dict."""
    sections, last = {}, None
    for m in _H_RE.finditer(md):
        if last:
            sections[last[1]] = md[last[0].end():m.start()].strip()
        last = (m, m.group(2).strip())
    if last:
        sections[last[1]] = md[last[0].end():].strip()
    if not sections:
        sections["FULL"] = md.strip()
    return sections

def sentence_split(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


# ---------------------------
# Tiny Python evaluators
# ---------------------------
def eval_eligibility(call_text: str, checklist_path: str) -> Tuple[float, Dict[str, Any]]:
    """
    CA5: Eligibility/Formalities via literal/regex checks.
    Score 0 if any 'hard' item missing; else coverage maps to 0–5.
    """
    details = {"missing_hard": [], "missing_soft": [], "hits": []}
    try:
        cfg = json.loads(pathlib.Path(checklist_path).read_text(encoding="utf-8"))
    except Exception:
        return 3.0, {"note": f"Checklist not found or unreadable: {checklist_path}"}

    def present(token: str) -> bool:
        # literal or simple regex if enclosed with slashes /.../
        token = token.strip()
        if len(token) >= 2 and token[0] == '/' and token[-1] == '/':
            pat = token[1:-1]
            return re.search(pat, call_text, re.I) is not None
        return token.lower() in call_text.lower()

    hard = cfg.get("hard", [])
    soft = cfg.get("soft", [])
    for h in hard:
        if present(h):
            details["hits"].append(h)
        else:
            details["missing_hard"].append(h)
    for s in soft:
        if present(s):
            details["hits"].append(s)
        else:
            details["missing_soft"].append(s)

    if details["missing_hard"]:
        score = 0.0
    else:
        tot = len(hard) + len(soft) if (hard or soft) else 1
        got = len(details["hits"])
        coverage = got / tot
        score = max(0.0, min(5.0, 1.0 + 4.0 * coverage))
    return round(score, 2), details


def eval_temporal(lfa_text: str) -> Tuple[float, Dict[str, Any]]:
    """
    LC4: Temporal completeness & rough ordering.
    Finds markers and checks if obvious sequences are non-decreasing.
    """
    markers = re.findall(r'\bM\d+\b|\bMonth\s*\d+\b|\bQ[1-4]\s*\d{4}\b|\b20\d{2}\b', lfa_text)
    uniq = list(dict.fromkeys(markers))  # preserve order
    info = {"markers_detected": uniq[:80], "unique_count": len(uniq), "ordering_notes": []}
    if not uniq:
        return 2.0, {"note": "No timeline markers found."}

    # Crude ordering check for M# sequences
    mnums = [int(x[1:]) for x in re.findall(r'M(\d+)', " ".join(uniq))]
    if mnums:
        unordered = any(mnums[i] > mnums[i+1] for i in range(len(mnums)-1))
        if unordered:
            info["ordering_notes"].append("Milestones appear out of order.")
    score = 2.0 + min(3.0, 0.25 * len(uniq))
    if info["ordering_notes"]:
        score = max(1.5, score - 0.5)
    return round(min(5.0, score), 2), info


def eval_duplication(lfa_text: str) -> Tuple[float, Dict[str, Any]]:
    """
    LC7: Exact & near-duplicate lines.
    """
    sents = sentence_split(lfa_text)
    seen, dupes = {}, []
    for i, s in enumerate(sents):
        key = s.lower()
        if key in seen:
            dupes.append({"first": seen[key], "repeat": i, "text": s[:180]})
        else:
            seen[key] = i
    near = []
    for i in range(len(sents) - 1):
        r = difflib.SequenceMatcher(None, sents[i], sents[i + 1]).ratio()
        if r > 0.92:
            near.append({"a": i, "b": i + 1, "ratio": round(r, 3), "text": sents[i][:160]})
    penalty = min(1.5, 0.1 * len(dupes) + 0.05 * len(near))
    score = round(max(0.0, 4.5 - penalty), 2)
    return score, {"exact": dupes[:30], "near": near[:30]}


def eval_readability(lfa_text: str) -> Tuple[float, Dict[str, Any]]:
    """
    CQ1 (optional): numeric readability anchor using textstat.
    """
    if not textstat:
        return 3.0, {"note": "textstat not installed; default score 3.0"}
    fre = textstat.flesch_reading_ease(lfa_text)
    # Map Flesch to 0–5 (roughly)
    if fre >= 60: s = 4.5
    elif fre >= 50: s = 3.8
    elif fre >= 40: s = 3.0
    elif fre >= 30: s = 2.2
    else: s = 1.5
    return round(s, 2), {"flesch": fre, "avg_sentence_len": textstat.avg_sentence_length(lfa_text)}


# ---------------------------
# LLM runner
# ---------------------------
def _load_prompt(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8")

def run_llm_criteria(model: str, system_prompt: str, user_payload: Dict[str, Any], temperature: float = 0.0) -> Dict[str, Any]:
    """
    One batch per block (CA/LC/CQ). Returns dict keyed by criterion.
    Uses LLM Provider with automatic fallback between Cursor CLI and OpenAI.
    """
    # Initialize LLM provider (prefers Cursor CLI, falls back to OpenAI)
    provider = LLMProvider(preferred_provider="openai")
    
    # Call LLM
    result = provider.call_llm(
        prompt=json.dumps(user_payload),
        model=model,
        system_prompt=system_prompt
    )
    
    if result["success"]:
        response_data = result["response"]
        
        # Handle Cursor CLI response format
        if result["provider"] == "cursor" and "result" in response_data:
            # Extract content from Cursor's result field
            content = response_data["result"]
            
            # Remove markdown code blocks if present
            if content.startswith("```json") and content.endswith("```"):
                content = content[7:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            # Also handle cases where there might be newlines
            content = content.replace("\\n", "\n").strip()
            
            # Parse JSON content
            try:
                response_data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON parsing failed. Content: {repr(content[:200])}")
                
                # Try to extract JSON from conversational response
                print("   🔧 Attempting to extract JSON from conversational response...")
                # Try multiple JSON extraction patterns
                json_patterns = [
                    r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON pattern
                    r'\{.*?\}(?=\s*$|\s*\n\s*$)',       # JSON ending pattern
                    r'\{.*\}',                          # Simple greedy pattern
                ]
                
                json_content = None
                for pattern in json_patterns:
                    json_match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
                    if json_match:
                        try:
                            json_content = json_match.group(0)
                            response_data = json.loads(json_content)
                            print(f"   ✅ Successfully extracted JSON using pattern: {pattern[:20]}...")
                            break
                        except json.JSONDecodeError:
                            continue
                
                if not json_content:
                    # Try to fall back to OpenAI if Cursor returns invalid JSON
                    print("   🔄 Attempting OpenAI fallback due to invalid JSON...")
                try:
                    from openai import OpenAI
                    client = OpenAI()
                    
                    # Use default model if none specified
                    if not model:
                        model = "gpt-4o-mini"
                    
                    # Build messages
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": json.dumps(user_payload)})
                    
                    # Make API call
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.0
                    )
                    
                    content = response.choices[0].message.content
                    
                    # Calculate cost
                    usage = response.usage
                    cost_info = {
                        "input_tokens": usage.prompt_tokens,
                        "output_tokens": usage.completion_tokens,
                        "total_tokens": usage.prompt_tokens + usage.completion_tokens,
                        "cost_usd": (usage.prompt_tokens / 1000 * 0.00015) + (usage.completion_tokens / 1000 * 0.0006)
                    }
                    
                    try:
                        response_data = json.loads(content)
                        response_data["_provider"] = "openai_fallback"
                        response_data["_cost_info"] = cost_info
                        print("   ✅ OpenAI fallback succeeded")
                        return response_data
                    except json.JSONDecodeError:
                        return {"_error": f"Both Cursor and OpenAI returned invalid JSON", "_provider": "both_failed"}
                        
                except Exception as fallback_error:
                    return {"_error": f"Failed to parse Cursor JSON response: {e}. Fallback to OpenAI also failed: {fallback_error}", "_provider": result["provider"]}
        
        # Add provider and cost info
        response_data["_provider"] = result["provider"]
        if "cost_info" in result:
            response_data["_cost_info"] = result["cost_info"]
        elif result["provider"] == "cursor":
            # Estimate token usage for Cursor CLI (since we don't get actual counts)
            prompt_text = json.dumps(user_payload) + (system_prompt or "")
            estimated_input_tokens = len(prompt_text.split()) * 1.3  # Rough estimate
            estimated_output_tokens = len(str(response_data)) * 0.8  # Rough estimate
            response_data["_cost_info"] = {
                "cost_usd": 0.0,  # Cursor CLI is free
                "input_tokens": int(estimated_input_tokens),
                "output_tokens": int(estimated_output_tokens), 
                "total_tokens": int(estimated_input_tokens + estimated_output_tokens),
                "provider": "cursor"
            }
        
        return response_data
    else:
        return {"_error": f"LLM call failed: {result['error']}", "_provider": result["provider"]}


# ---------------------------
# Test mode helper
# ---------------------------
def _generate_test_results(lfa_text: str, call_text: str, model: str) -> Dict[str, Any]:
    """Generate mock results for test mode without API calls."""
    return {
        "meta": {
            "engine_version": "0.2.0-test",
            "model": f"{model} (TEST MODE)",
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "test_mode": True,
            "note": "Results generated in test mode - no API calls made",
            "cost_estimate": {
                "input_tokens_estimated": 50000,
                "output_tokens_estimated": 3000,
                "cost_per_1k_input": 0.00015 if "gpt-4o-mini" in model else 0.0015,
                "cost_per_1k_output": 0.0006 if "gpt-4o-mini" in model else 0.002,
                "estimated_total_cost": "$0.008" if "gpt-4o-mini" in model else "$0.081",
                "currency": "USD"
            }
        },
        "scores": {
            "CA": {
                "CA1": 4.0, "CA2": 3.5, "CA3": 4.2, "CA4": 3.8, "CA5": 4.5, "CA6": 4.1,
                "weight": 0.30, "subtotal": 4.02
            },
            "LC": {
                "LC1": 3.8, "LC2": 4.0, "LC3": 3.5, "LC4": 4.2,
                "weight": 0.50, "subtotal": 3.88
            },
            "CQ": {
                "CQ1": 4.0, "CQ2": 3.8, "CQ3": 4.2,
                "weight": 0.20, "subtotal": 4.0
            },
            "total": 3.95,
            "band": "Strong"
        },
        "findings": {
            "CA1": {
                "evidence": [{"quote": "Project objectives align with call aims", "loc": "Objectives section"}],
                "gaps": ["Could strengthen alignment with specific call priorities"],
                "fixes": ["Add explicit mapping to call objectives"]
            },
            "LC1": {
                "evidence": [{"quote": "Clear hierarchy from goal to activities", "loc": "Logic Framework"}],
                "gaps": ["Some outcomes could be more specific"],
                "fixes": ["Refine outcome descriptions"]
            },
            "CQ1": {
                "evidence": [{"quote": "Good use of specific metrics and targets", "loc": "KPIs section"}],
                "gaps": ["Some claims could be more quantified"],
                "fixes": ["Add more specific numerical targets"]
            }
        },
        "report_md_path": "review_report_test.md"
    }

def _generate_markdown_report(results: Dict[str, Any]) -> str:
    """Generate markdown report from results."""
    lines = []
    project_name = results.get('meta', {}).get('project_name', 'Project')
    lines.append(f"# {project_name} - Review Report")
    lines.append(f"- **Total**: {results['scores']['total']} / 5  ({results['scores']['band']})")
    
    # Check for missing scores and add notes
    ca_score = results['scores']['CA']['subtotal']
    lc_score = results['scores']['LC']['subtotal']
    cq_score = results['scores']['CQ']['subtotal']
    
    missing_scores = []
    if ca_score == 0.0:
        missing_scores.append("Call Alignment")
    if lc_score == 0.0:
        missing_scores.append("Logic Consistency")
    if cq_score == 0.0:
        missing_scores.append("Content Quality")
    
    if missing_scores:
        lines.append(f"- **Note**: {', '.join(missing_scores)} evaluation failed due to technical issues")
    
    lines.append(f"- **Call Alignment (30%)**: {ca_score}")
    lines.append(f"- **Logic Consistency (50%)**: {lc_score}")
    lines.append(f"- **Content Quality (20%)**: {cq_score}")
    lines.append(f"- **Review Phase**: Phase A - Logic Framework Analysis")
    lines.append(f"- Engine: v{results['meta']['engine_version']} | Model: {results['meta']['model']}")
    
    # Add usage and provider information
    if "cost_tracking" in results["meta"]:
        cost_info = results["meta"]["cost_tracking"]
        provider_info = ""
        if "provider_usage" in cost_info:
            providers = list(cost_info["provider_usage"].keys())
            provider_info = f" | Providers: {', '.join(providers)}"
        lines.append(f"- **Usage**: Tokens: {cost_info['total_tokens']:,} | API Calls: {cost_info['api_calls']}{provider_info}")
    elif "cost_estimate" in results["meta"]:
        cost_info = results["meta"]["cost_estimate"]
        lines.append(f"- **Usage**: Tokens: {cost_info['input_tokens_estimated']:,} input + {cost_info['output_tokens_estimated']:,} output")
    
    lines.append("\n---\n")

    # Add score explanation (right after header info)
    lines.append("## Score Explanation")
    lines.append("")
    lines.append("Each criterion is scored on a scale of 0-5, where:")
    lines.append("")
    lines.append("- **5 - Excellent**: Outstanding performance with no significant gaps")
    lines.append("- **4 - Good**: Strong performance with minor areas for improvement")
    lines.append("- **3 - Adequate**: Acceptable performance with some gaps to address")
    lines.append("- **2 - Needs Work**: Below average performance with significant gaps")
    lines.append("- **1 - Poor**: Major issues requiring substantial improvement")
    lines.append("- **0 - Critical**: Severe problems or missing essential elements")
    lines.append("")
    lines.append("**Total Score Calculation:** Call Alignment (30%) + Logic Consistency (50%) + Content Quality (20%) = Overall Score")
    lines.append("")
    
    # Add executive summary
    lines.append("## Executive Summary")
    lines.append("")
    
    # Add executive summary content
    total_score = results['scores']['total']
    band = results['scores']['band']
    
    if missing_scores:
        lines.append(f"**Note:** {', '.join(missing_scores)} evaluation failed due to technical issues.")
        lines.append("")
    
    lines.append(f"This proposal received an overall score of {total_score:.2f}/5.0, placing it in the '{band}' category.")
    lines.append("")
    
    # Add specific feedback based on scores
    if ca_score >= 4.0:
        lines.append("The proposal shows strong alignment with the call requirements.")
    elif ca_score >= 3.0:
        lines.append("The proposal demonstrates adequate alignment with the call requirements, with room for improvement.")
    else:
        lines.append("The proposal requires significant improvements in call alignment.")
    
    if lc_score >= 4.0:
        lines.append("The logical framework is well-structured and internally consistent.")
    elif lc_score >= 3.0:
        lines.append("The logical framework shows good structure but has some consistency issues.")
    else:
        lines.append("The logical framework needs substantial restructuring for better consistency.")
    
    if cq_score >= 4.0:
        lines.append("The content quality is high with clear, well-supported arguments.")
    elif cq_score >= 3.0:
        lines.append("The content quality is adequate but could benefit from more specific evidence and clearer language.")
    else:
        lines.append("The content quality needs significant improvement in clarity and evidence.")
    
    lines.append("")
    lines.append("Detailed findings and recommendations are provided in the following sections.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Define criteria names and explanations
    criteria_names = {
        "CA1": "Objectives alignment",
        "CA2": "Scope fit", 
        "CA3": "Outcomes/Impacts alignment",
        "CA4": "Evaluation coverage",
        "CA5": "LFA-Call alignment completeness",
        "CA6": "Terminology/definitions alignment",
        "LC1": "Logical Flow",
        "LC2": "Measurable Outcomes", 
        "LC3": "Activity-Outcome Linkage",
        "LC4": "Implementation Feasibility",
        "CQ1": "Clarity & Specificity",
        "CQ2": "Actionable Content",
        "CQ3": "Professional Presentation"
    }
    
    criteria_explanations = {
        "CA1": "How well the LFA objectives align with the call's main aims and requirements",
        "CA2": "Whether the LFA activities, target populations, and geographies fit within the call's scope",
        "CA3": "How well the LFA outcomes address the call's expected impacts and success criteria",
        "CA4": "Whether the LFA addresses the call's evaluation criteria (Excellence, Impact, Implementation)",
        "CA5": "Overall completeness of alignment between LFA elements and call requirements",
        "CA6": "Consistency in using call-specific terminology and definitions",
        "LC1": "Clear progression from Goal → Purpose → Outcomes → Activities",
        "LC2": "Specific, quantifiable outcomes with clear indicators and targets",
        "LC3": "Clear connection between activities and outcomes they enable",
        "LC4": "Activities are realistic, achievable, and well-defined",
        "CQ1": "Clear, specific language with concrete examples and quantified claims",
        "CQ2": "Content that can be implemented, measured, and tracked with clear next steps",
        "CQ3": "Well-structured, professional writing with clear organization and minimal redundancy"
    }
    
    criteria_weights = {
        "CA": 30,
        "LC": 50,
        "CQ": 20
    }

    # Order findings by criterion name for stability
    for crit in sorted(results["findings"].keys()):
        detail = results["findings"][crit]
        if not crit.endswith("_ERROR"):
            explanation = criteria_explanations.get(crit, f"{crit}: Evaluation criterion")
            block_key = crit[:2]
            score = results["scores"].get(block_key, {}).get(crit, 0)
            weight = criteria_weights.get(crit[:2], 20)
            
            # Use full criterion name
            criterion_name = criteria_names.get(crit, crit)
            lines.append(f"## {crit}: {criterion_name}")
            lines.append(f"**Score:** {score}/5.0 | **Weight:** {weight}%")
            lines.append("")
            lines.append(f"**What we're evaluating:** {explanation}")
            lines.append("")
            
        if "evidence" in detail:
            ev = detail["evidence"]
            if isinstance(ev, list) and ev:
                lines.append("**Strengths:**")
                for e in ev[:8]:
                    if isinstance(e, dict):
                        q = e.get("quote", "")
                        loc = e.get("loc", "")
                        lines.append(f"- \"{q}\" — _{loc}_")
                    else:
                        # Handle narrative format - no bullets, just paragraph text
                        lines.append(f"{e}")
                lines.append("")
        if "gaps" in detail:
            gaps = detail["gaps"]
            if isinstance(gaps, list) and gaps:
                lines.append("**Areas for Improvement:**")
                for g in gaps[:8]:
                    # Handle narrative format - no bullets, just paragraph text
                    lines.append(f"{g}")
                lines.append("")
        if "fixes" in detail:
            fixes = detail["fixes"]
            if isinstance(fixes, list) and fixes:
                lines.append("**Suggestions to straight copy-paste into the document:**")
                for f in fixes[:8]:
                    lines.append(f"{f}")
                lines.append("")
        if "suggested_text" in detail:
            suggestions = detail["suggested_text"]
            if isinstance(suggestions, list) and suggestions:
                lines.append("**Suggested Text:**")
                lines.append("")
                for s in suggestions[:8]:
                    lines.append(f"> {s}")
                    lines.append("")
        if "details" in detail:
            # show compact JSON for python checks
            try:
                compact = json.dumps(detail["details"], indent=2)[:2000]
                lines.append("**Technical Details:**")
                lines.append(f"```json\n{compact}\n```")
            except Exception:
                pass
        lines.append("")
    
    return "\n".join(lines)


# ---------------------------
# Engine entrypoint
# ---------------------------
def run_review(
    lfa_md_path: str,
    call_md_path: str,
    run_config_path: str,
    model: str = "gpt-4o-mini",
    project_name: str = "Project",
    temperature: float = 0.0,
    prompts_dir: str = "prompts",
    eligibility_checklist_path: str = "eligibility_checklist.json",
    return_markdown_report: bool = True,
    max_chars_call: int = 10000,
    max_chars_lfa: int = 15000,
    test_mode: bool = False,
) -> Dict[str, Any]:
    """
    Main entrypoint. Returns result dict. Optionally writes review_report.md.
    """
    # -- Load inputs
    lfa_text = pathlib.Path(lfa_md_path).read_text(encoding="utf-8")
    call_text = pathlib.Path(call_md_path).read_text(encoding="utf-8")
    cfg = json.loads(pathlib.Path(run_config_path).read_text(encoding="utf-8"))
    
    lfa_sections = split_markdown(lfa_text)
    call_sections = split_markdown(call_text)
    
    # -- Test mode: return mock results without API calls
    if test_mode:
        test_results = _generate_test_results(lfa_text, call_text, model)
        # Generate markdown report for test mode if requested
        if return_markdown_report:
            test_results["report_md"] = _generate_markdown_report(test_results)
        return test_results

    # -- Prep result shell
    results: Dict[str, Any] = {
        "meta": {
            "engine_version": "0.2.0",
            "model": model,
            "project_name": project_name,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "prompt_versions": {"CA": "v1", "LC": "v1", "CQ": "v1"},
            "paths": {
                "lfa": str(pathlib.Path(lfa_md_path).resolve()),
                "call": str(pathlib.Path(call_md_path).resolve()),
                "criteria": str(pathlib.Path(run_config_path).resolve())
            },
            "cost_tracking": {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "api_calls": 0,
                "currency": "USD"
            }
        },
        "scores": {"CA": {}, "LC": {}, "CQ": {}, "total": 0.0, "band": "NA"},
        "findings": {}
    }

    # -------------------
    # Python-only criteria
    # -------------------
    def add_score(block: str, crit: str, score: float, details: Dict[str, Any]):
        results["scores"][block][crit] = float(score)
        # Keep details under findings[crit]
        if crit not in results["findings"]:
            results["findings"][crit] = {}
        results["findings"][crit]["details"] = details

    routing = cfg.get("criteria", {})

    # All criteria are now handled by LLM evaluation

    # -------------------
    # LLM batches by block
    # -------------------
    # Helper: call a block if at least one criterion routes to LLM
    def _run_block(block: str, prompt_file: str, criteria_list: List[str], payload: Dict[str, Any]):
        needed = [c for c in criteria_list if routing.get(c) == "llm"]
        if not needed:
            return
        system_prompt = _load_prompt(os.path.join(prompts_dir, prompt_file))
        payload = dict(payload)  # shallow copy
        payload["criteria"] = needed
        out = run_llm_criteria(model, system_prompt, payload, temperature)
        
        # Track costs and provider info
        if "_cost_info" in out:
            cost_info = out["_cost_info"]
            results["meta"]["cost_tracking"]["total_cost_usd"] += cost_info["cost_usd"]
            results["meta"]["cost_tracking"]["total_tokens"] += cost_info.get("total_tokens", 0)
            results["meta"]["cost_tracking"]["api_calls"] += 1
        
        # Track provider usage
        if "_provider" in out:
            provider = out["_provider"]
            if "provider_usage" not in results["meta"]["cost_tracking"]:
                results["meta"]["cost_tracking"]["provider_usage"] = {}
            if provider not in results["meta"]["cost_tracking"]["provider_usage"]:
                results["meta"]["cost_tracking"]["provider_usage"][provider] = 0
            results["meta"]["cost_tracking"]["provider_usage"][provider] += 1
        
        if "_error" in out:
            # record error and skip scoring
            results["findings"][f"{block}_LLM_ERROR"] = out
            return
        for k in needed:
            item = out.get(k, {})
            score = float(item.get("score", 3.0))
            results["scores"][block][k] = score
            # Store structured findings
            findings = {kk: vv for kk, vv in item.items() if kk != "score" and kk != "_cost_info"}
            results["findings"][k] = findings

    # Build compact payloads
    call_outline = list(call_sections.keys())[:30]
    lfa_outline = list(lfa_sections.keys())[:60]
    call_excerpt = call_text[:max_chars_call]
    lfa_excerpt = lfa_text[:max_chars_lfa]

    # CA block
    print("⏱️  Starting Call Alignment (CA) evaluation...")
    ca_start = time.time()
    _run_block(
        "CA",
        "call_alignment.txt",
        ["CA1","CA2","CA3","CA4","CA5","CA6"],
        {
            "call_outline": call_outline,
            "lfa_outline": lfa_outline,
            "call_excerpts": call_excerpt,
            "lfa_excerpts": lfa_excerpt
        }
    )
    ca_time = time.time() - ca_start
    print(f"⏱️  CA block completed in {ca_time:.2f}s")

    # LC block
    print("⏱️  Starting Logic Consistency (LC) evaluation...")
    lc_start = time.time()
    _run_block(
        "LC",
        "internal_consistency.txt",
        ["LC1","LC2","LC3","LC4"],
        {
            "lfa_outline": lfa_outline,
            "lfa_excerpts": lfa_excerpt
        }
    )
    lc_time = time.time() - lc_start
    print(f"⏱️  LC block completed in {lc_time:.2f}s")

    # CQ block
    print("⏱️  Starting Content Quality (CQ) evaluation...")
    cq_start = time.time()
    _run_block(
        "CQ",
        "content_quality.txt",
        ["CQ1","CQ2","CQ3"],
        {
            "lfa_outline": lfa_outline,
            "lfa_excerpts": lfa_excerpt
        }
    )
    cq_time = time.time() - cq_start
    print(f"⏱️  CQ block completed in {cq_time:.2f}s")

    # -------------------
    # Weighted totals
    # -------------------
    def _avg(d: Dict[str, float]) -> float:
        vals = [v for k, v in d.items() if isinstance(v, (int, float))]
        return sum(vals) / len(vals) if vals else 0.0

    ca = _avg(results["scores"]["CA"])
    lc = _avg(results["scores"]["LC"])
    cq = _avg(results["scores"]["CQ"])

    results["scores"]["CA"]["weight"] = 0.30
    results["scores"]["LC"]["weight"] = 0.50
    results["scores"]["CQ"]["weight"] = 0.20
    results["scores"]["CA"]["subtotal"] = round(ca, 2)
    results["scores"]["LC"]["subtotal"] = round(lc, 2)
    results["scores"]["CQ"]["subtotal"] = round(cq, 2)

    total = 0.30 * ca + 0.50 * lc + 0.20 * cq
    results["scores"]["total"] = round(total, 2)
    results["scores"]["band"] = (
        "Outstanding" if total >= 4.5 else
        "Strong" if total >= 4.0 else
        "Adequate" if total >= 3.5 else
        "Needs Work"
    )

    # -------------------
    # Markdown report
    # -------------------
    if return_markdown_report:
        results["report_md"] = _generate_markdown_report(results)
        out = pathlib.Path("review_report.md")
        out.write_text(results["report_md"], encoding="utf-8")
        results["report_md_path"] = str(out.resolve())

    return results


# ---------------------------
# Split review entry points
# ---------------------------

def run_structural_review(
    lfa_md_path: str,
    lfa_template_path: str = "",
    run_config_path: str = "criteria.json",
    model: str = "gpt-4o-mini",
    project_name: str = "Project",
    temperature: float = 0.0,
    prompts_dir: str = "prompts",
    return_markdown_report: bool = True,
    max_chars_lfa: int = 30000,
    test_mode: bool = False,
) -> Dict[str, Any]:
    """
    Layer 1: Evaluate LFA structural/methodological quality.
    Runs LC + CQ blocks only. No call document needed.
    Compares against LFA template for structural completeness.
    """
    lfa_text = pathlib.Path(lfa_md_path).read_text(encoding="utf-8")
    cfg = json.loads(pathlib.Path(run_config_path).read_text(encoding="utf-8"))

    lfa_template_text = ""
    if lfa_template_path and pathlib.Path(lfa_template_path).exists():
        lfa_template_text = pathlib.Path(lfa_template_path).read_text(encoding="utf-8")

    lfa_sections = split_markdown(lfa_text)

    results: Dict[str, Any] = {
        "meta": {
            "engine_version": "0.2.0",
            "model": model,
            "project_name": project_name,
            "review_type": "structural",
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "prompt_versions": {"LC": "v1", "CQ": "v1"},
            "paths": {
                "lfa": str(pathlib.Path(lfa_md_path).resolve()),
                "template": str(pathlib.Path(lfa_template_path).resolve()) if lfa_template_path else "",
            },
            "cost_tracking": {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "api_calls": 0,
                "currency": "USD"
            }
        },
        "scores": {"LC": {}, "CQ": {}, "total": 0.0, "band": "NA"},
        "findings": {}
    }

    routing = cfg.get("criteria", {})

    def _run_block_local(block, prompt_file, criteria_list, payload):
        needed = [c for c in criteria_list if routing.get(c) == "llm"]
        if not needed:
            return
        system_prompt = _load_prompt(os.path.join(prompts_dir, prompt_file))
        payload = dict(payload)
        payload["criteria"] = needed
        out = run_llm_criteria(model, system_prompt, payload, temperature)
        if "_cost_info" in out:
            ci = out["_cost_info"]
            results["meta"]["cost_tracking"]["total_cost_usd"] += ci["cost_usd"]
            results["meta"]["cost_tracking"]["total_tokens"] += ci.get("total_tokens", 0)
            results["meta"]["cost_tracking"]["api_calls"] += 1
        if "_provider" in out:
            prov = out["_provider"]
            pu = results["meta"]["cost_tracking"].setdefault("provider_usage", {})
            pu[prov] = pu.get(prov, 0) + 1
        if "_error" in out:
            results["findings"][f"{block}_LLM_ERROR"] = out
            return
        for k in needed:
            item = out.get(k, {})
            score = float(item.get("score", 3.0))
            results["scores"][block][k] = score
            findings = {kk: vv for kk, vv in item.items() if kk != "score" and kk != "_cost_info"}
            results["findings"][k] = findings

    lfa_outline = list(lfa_sections.keys())[:60]
    lfa_excerpt = lfa_text[:max_chars_lfa]

    # LC block — include template for structural comparison
    print("⏱️  Starting Structural Review: Logic Consistency (LC)...")
    lc_start = time.time()
    lc_payload = {
        "lfa_outline": lfa_outline,
        "lfa_excerpts": lfa_excerpt,
    }
    if lfa_template_text:
        lc_payload["lfa_template"] = lfa_template_text
    _run_block_local("LC", "internal_consistency.txt", ["LC1", "LC2", "LC3", "LC4"], lc_payload)
    print(f"⏱️  LC block completed in {time.time() - lc_start:.2f}s")

    # CQ block
    print("⏱️  Starting Structural Review: Content Quality (CQ)...")
    cq_start = time.time()
    _run_block_local("CQ", "content_quality.txt", ["CQ1", "CQ2", "CQ3"], {
        "lfa_outline": lfa_outline,
        "lfa_excerpts": lfa_excerpt,
    })
    print(f"⏱️  CQ block completed in {time.time() - cq_start:.2f}s")

    # Weighted total: 70% LC + 30% CQ
    def _avg(d):
        vals = [v for k, v in d.items() if isinstance(v, (int, float))]
        return sum(vals) / len(vals) if vals else 0.0

    lc = _avg(results["scores"]["LC"])
    cq = _avg(results["scores"]["CQ"])
    results["scores"]["LC"]["weight"] = 0.70
    results["scores"]["CQ"]["weight"] = 0.30
    results["scores"]["LC"]["subtotal"] = round(lc, 2)
    results["scores"]["CQ"]["subtotal"] = round(cq, 2)
    total = 0.70 * lc + 0.30 * cq
    results["scores"]["total"] = round(total, 2)
    results["scores"]["band"] = (
        "Outstanding" if total >= 4.5 else
        "Strong" if total >= 4.0 else
        "Adequate" if total >= 3.5 else
        "Needs Work"
    )

    if return_markdown_report:
        results["report_md"] = _generate_structural_report(results)
        out_path = pathlib.Path("structural_review_report.md")  # temp, moved by caller
        out_path.write_text(results["report_md"], encoding="utf-8")
        results["report_md_path"] = str(out_path.resolve())

    return results


def run_alignment_review(
    lfa_md_path: str,
    call_md_path: str,
    run_config_path: str = "criteria.json",
    model: str = "gpt-4o-mini",
    project_name: str = "Project",
    temperature: float = 0.0,
    prompts_dir: str = "prompts",
    eligibility_checklist_path: str = "eligibility_checklist.json",
    return_markdown_report: bool = True,
    max_chars_call: int = 50000,
    max_chars_lfa: int = 30000,
    test_mode: bool = False,
) -> Dict[str, Any]:
    """
    Layer 2: Evaluate LFA alignment with call requirements.
    Runs CA block only.
    """
    lfa_text = pathlib.Path(lfa_md_path).read_text(encoding="utf-8")
    call_text = pathlib.Path(call_md_path).read_text(encoding="utf-8")
    cfg = json.loads(pathlib.Path(run_config_path).read_text(encoding="utf-8"))

    lfa_sections = split_markdown(lfa_text)
    call_sections = split_markdown(call_text)

    results: Dict[str, Any] = {
        "meta": {
            "engine_version": "0.2.0",
            "model": model,
            "project_name": project_name,
            "review_type": "alignment",
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "prompt_versions": {"CA": "v1"},
            "paths": {
                "lfa": str(pathlib.Path(lfa_md_path).resolve()),
                "call": str(pathlib.Path(call_md_path).resolve()),
            },
            "cost_tracking": {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "api_calls": 0,
                "currency": "USD"
            }
        },
        "scores": {"CA": {}, "total": 0.0, "band": "NA"},
        "findings": {}
    }

    routing = cfg.get("criteria", {})

    def _run_block_local(block, prompt_file, criteria_list, payload):
        needed = [c for c in criteria_list if routing.get(c) == "llm"]
        if not needed:
            return
        system_prompt = _load_prompt(os.path.join(prompts_dir, prompt_file))
        payload = dict(payload)
        payload["criteria"] = needed
        out = run_llm_criteria(model, system_prompt, payload, temperature)
        if "_cost_info" in out:
            ci = out["_cost_info"]
            results["meta"]["cost_tracking"]["total_cost_usd"] += ci["cost_usd"]
            results["meta"]["cost_tracking"]["total_tokens"] += ci.get("total_tokens", 0)
            results["meta"]["cost_tracking"]["api_calls"] += 1
        if "_provider" in out:
            prov = out["_provider"]
            pu = results["meta"]["cost_tracking"].setdefault("provider_usage", {})
            pu[prov] = pu.get(prov, 0) + 1
        if "_error" in out:
            results["findings"][f"{block}_LLM_ERROR"] = out
            return
        for k in needed:
            item = out.get(k, {})
            score = float(item.get("score", 3.0))
            results["scores"][block][k] = score
            findings = {kk: vv for kk, vv in item.items() if kk != "score" and kk != "_cost_info"}
            results["findings"][k] = findings

    call_outline = list(call_sections.keys())[:30]
    lfa_outline = list(lfa_sections.keys())[:60]
    call_excerpt = call_text[:max_chars_call]
    lfa_excerpt = lfa_text[:max_chars_lfa]

    print("⏱️  Starting Alignment Review: Call Alignment (CA)...")
    ca_start = time.time()
    _run_block_local(
        "CA", "call_alignment.txt",
        ["CA1", "CA2", "CA3", "CA4", "CA5", "CA6"],
        {
            "call_outline": call_outline,
            "lfa_outline": lfa_outline,
            "call_excerpts": call_excerpt,
            "lfa_excerpts": lfa_excerpt,
        }
    )
    print(f"⏱️  CA block completed in {time.time() - ca_start:.2f}s")

    def _avg(d):
        vals = [v for k, v in d.items() if isinstance(v, (int, float))]
        return sum(vals) / len(vals) if vals else 0.0

    ca = _avg(results["scores"]["CA"])
    results["scores"]["CA"]["weight"] = 1.00
    results["scores"]["CA"]["subtotal"] = round(ca, 2)
    total = ca
    results["scores"]["total"] = round(total, 2)
    results["scores"]["band"] = (
        "Outstanding" if total >= 4.5 else
        "Strong" if total >= 4.0 else
        "Adequate" if total >= 3.5 else
        "Needs Work"
    )

    if return_markdown_report:
        results["report_md"] = _generate_alignment_report(results)
        out_path = pathlib.Path("alignment_review_report.md")
        out_path.write_text(results["report_md"], encoding="utf-8")
        results["report_md_path"] = str(out_path.resolve())

    return results


def _generate_structural_report(results: Dict[str, Any]) -> str:
    """Generate markdown report for structural review (LC + CQ only)."""
    lines = []
    project_name = results.get('meta', {}).get('project_name', 'Project')
    lines.append(f"# {project_name} - Structural Review Report")
    lines.append(f"_Review type: LFA Structural & Methodological Quality_")
    lines.append("")
    lines.append(f"- **Total**: {results['scores']['total']} / 5  ({results['scores']['band']})")

    lc_score = results['scores']['LC'].get('subtotal', 0)
    cq_score = results['scores']['CQ'].get('subtotal', 0)

    lines.append(f"- **Logic Consistency (70%)**: {lc_score}")
    lines.append(f"- **Content Quality (30%)**: {cq_score}")

    if "cost_tracking" in results["meta"]:
        ci = results["meta"]["cost_tracking"]
        lines.append(f"- **Usage**: Tokens: {ci['total_tokens']:,} | API Calls: {ci['api_calls']}")

    lines.append(f"- Engine: v{results['meta']['engine_version']} | Model: {results['meta']['model']}")
    lines.append("\n---\n")

    lines.append("## What This Review Covers")
    lines.append("")
    lines.append("This review evaluates the LFA **on its own merits** — structural quality, logical coherence,")
    lines.append("and methodological correctness — independent of any specific funding call.")
    lines.append("")
    lines.append("---\n")

    _append_findings(lines, results)
    return "\n".join(lines)


def _generate_alignment_report(results: Dict[str, Any]) -> str:
    """Generate markdown report for alignment review (CA only)."""
    lines = []
    project_name = results.get('meta', {}).get('project_name', 'Project')
    lines.append(f"# {project_name} - Call Alignment Review Report")
    lines.append(f"_Review type: LFA vs Call Requirements Alignment_")
    lines.append("")
    lines.append(f"- **Total**: {results['scores']['total']} / 5  ({results['scores']['band']})")

    ca_score = results['scores']['CA'].get('subtotal', 0)
    lines.append(f"- **Call Alignment (100%)**: {ca_score}")

    if "cost_tracking" in results["meta"]:
        ci = results["meta"]["cost_tracking"]
        lines.append(f"- **Usage**: Tokens: {ci['total_tokens']:,} | API Calls: {ci['api_calls']}")

    lines.append(f"- Engine: v{results['meta']['engine_version']} | Model: {results['meta']['model']}")
    lines.append("\n---\n")

    lines.append("## What This Review Covers")
    lines.append("")
    lines.append("This review evaluates how well the LFA aligns with the specific funding call requirements,")
    lines.append("including objectives, scope, expected outcomes, evaluation criteria, and terminology.")
    lines.append("")
    lines.append("---\n")

    _append_findings(lines, results)
    return "\n".join(lines)


def _append_findings(lines: List[str], results: Dict[str, Any]):
    """Shared helper to append criterion findings to report lines."""
    criteria_names = {
        "CA1": "Objectives alignment", "CA2": "Scope fit",
        "CA3": "Outcomes/Impacts alignment", "CA4": "Evaluation coverage",
        "CA5": "LFA-Call alignment completeness", "CA6": "Terminology/definitions alignment",
        "LC1": "Logical Flow", "LC2": "Measurable Outcomes",
        "LC3": "Activity-Outcome Linkage", "LC4": "Implementation Feasibility",
        "CQ1": "Clarity & Specificity", "CQ2": "Actionable Content",
        "CQ3": "Professional Presentation",
    }

    for crit in sorted(results["findings"].keys()):
        detail = results["findings"][crit]
        if crit.endswith("_ERROR"):
            continue
        block_key = crit[:2]
        score = results["scores"].get(block_key, {}).get(crit, 0)
        name = criteria_names.get(crit, crit)
        lines.append(f"## {crit}: {name}")
        lines.append(f"**Score:** {score}/5.0")
        lines.append("")

        if "evidence" in detail:
            ev = detail["evidence"]
            if isinstance(ev, list) and ev:
                lines.append("**Strengths:**")
                for e in ev[:8]:
                    if isinstance(e, dict):
                        lines.append(f"- \"{e.get('quote', '')}\" — _{e.get('loc', '')}_")
                    else:
                        lines.append(f"{e}")
                lines.append("")
        if "gaps" in detail:
            gaps = detail["gaps"]
            if isinstance(gaps, list) and gaps:
                lines.append("**Areas for Improvement:**")
                for g in gaps[:8]:
                    lines.append(f"{g}")
                lines.append("")
        if "fixes" in detail:
            fixes = detail["fixes"]
            if isinstance(fixes, list) and fixes:
                lines.append("**Recommendations:**")
                for f in fixes[:8]:
                    lines.append(f"{f}")
                lines.append("")
        if "suggested_text" in detail:
            suggestions = detail["suggested_text"]
            if isinstance(suggestions, list) and suggestions:
                lines.append("**Suggested Text:**")
                lines.append("")
                for s in suggestions[:8]:
                    lines.append(f"> {s}")
                    lines.append("")
        lines.append("")


# ---------------------------
# Simple CLI usage (optional)
# ---------------------------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Run LFA/Call review.")
    p.add_argument("--lfa", required=True, help="Path to LFA Markdown")
    p.add_argument("--call", required=True, help="Path to Call Markdown")
    p.add_argument("--criteria", default="criteria.json", help="Path to criteria.json")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--project-name", default="Project")
    p.add_argument("--temp", type=float, default=0.0)
    p.add_argument("--no-report", action="store_true")
    p.add_argument("--elig", default="eligibility_checklist.json")
    args = p.parse_args()

    res = run_review(
        lfa_md_path=args.lfa,
        call_md_path=args.call,
        run_config_path=args.criteria,
        model=args.model,
        project_name=args.project_name,
        temperature=args.temp,
        eligibility_checklist_path=args.elig,
        return_markdown_report=not args.no_report
    )
    print(json.dumps(res, indent=2))
