import httpx
import json
import re
import logging
from app.config import settings

logger = logging.getLogger(__name__)


OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MAX_CALLS_IN_PROMPT = 30
MAX_RESULTS = 20

DOMAIN_TERM_MAP: dict[str, list[str]] = {
    "fisheries": ["fishery", "fisheries", "fishing", "visserij", "seafood", "fish processing"],
    "aquaculture": ["aquaculture", "mariculture", "fish farm", "shellfish farm", "hatchery"],
    "seaweed": ["seaweed", "algae", "algal", "macroalgae", "kelp"],
    "seafood": ["seafood", "fish processing", "cold chain", "value-added fish"],
    "blue biotech": ["blue biotech", "marine biotech", "marine bioactive", "marine biotechnology"],
    "marine conservation": ["marine conservation", "biodiversity", "ecosystem restoration", "habitat restoration"],
    "maritime": ["maritime", "marine", "coastal", "port operations", "shipping"],
}

EXCLUDED_ADJACENT_TERMS = {
    "renewable energy",
    "offshore wind",
    "wind farm",
    "hydrogen",
    "solar",
    "photovoltaic",
    "pv",
}

NON_CALL_TERMS = {
    "announcement",
    "announcements",
    "news",
    "nieuws",
    "calendar",
    "kalender",
    "tenderkalender",
    "comes soon",
    "komt eraan",
    "coming soon",
    "event",
    "events",
    "press release",
}


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_keywords(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _normalize_whitespace(_safe_text(item)).lower()
        if text:
            out.append(text)
    return out


def _normalize_domains(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _normalize_whitespace(_safe_text(item)).lower()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _build_domain_terms(focus_domains: list[str] | None) -> set[str]:
    domains = _normalize_domains(focus_domains)
    terms: set[str] = set()
    for domain in domains:
        terms.add(domain)
        if domain in DOMAIN_TERM_MAP:
            terms.update(t.lower() for t in DOMAIN_TERM_MAP[domain])
            continue
        for key, mapped in DOMAIN_TERM_MAP.items():
            if key in domain or domain in key:
                terms.update(t.lower() for t in mapped)
        parts = [p for p in re.split(r"[\s/&,-]+", domain) if len(p) >= 4]
        terms.update(parts)
    return {t for t in terms if t}


def _call_text_blob(call: dict) -> str:
    title = _normalize_whitespace(_safe_text(call.get("title"))).lower()
    summary = _normalize_whitespace(_safe_text(call.get("summary"))).lower()
    url = _normalize_whitespace(_safe_text(call.get("url"))).lower()
    return f"{title} {summary} {url}".strip()


def _is_non_call_item(call: dict) -> bool:
    title = _normalize_whitespace(_safe_text(call.get("title"))).lower()
    summary = _normalize_whitespace(_safe_text(call.get("summary"))).lower()
    url = _normalize_whitespace(_safe_text(call.get("url"))).lower()
    blob = f"{title} {summary} {url}"
    return any(term in blob for term in NON_CALL_TERMS)


def _passes_domain_gate(call: dict, domain_terms: set[str]) -> bool:
    if not domain_terms:
        return True
    blob = _call_text_blob(call)
    if not blob:
        return False
    has_domain_hit = any(term in blob for term in domain_terms)
    if not has_domain_hit:
        return False
    # Reject adjacent sectors unless explicitly part of selected domains.
    adjacent_hit = any(term in blob for term in EXCLUDED_ADJACENT_TERMS)
    if adjacent_hit:
        explicit_adjacent = any(adj in domain_terms for adj in EXCLUDED_ADJACENT_TERMS)
        if not explicit_adjacent:
            return False
    return True


def _build_feedback_summary(feedback_items: list[dict] | None, max_per_label: int = 8) -> str:
    if not feedback_items:
        return "No feedback history available."

    relevant_lines: list[str] = []
    not_relevant_lines: list[str] = []
    for item in feedback_items:
        title = _normalize_whitespace(_safe_text(item.get("title")))
        summary = _normalize_whitespace(_safe_text(item.get("summary")))
        source_keywords = ", ".join(_normalize_keywords(item.get("source_keywords"))[:6]) or "None"
        short_summary = summary[:180] if summary else ""
        sample = f"- Title: {title or 'Untitled'} | Summary: {short_summary or 'None'} | Source keywords: {source_keywords}"
        label = _safe_text(item.get("label")).lower()
        if label == "relevant" and len(relevant_lines) < max_per_label:
            relevant_lines.append(sample)
        elif label == "not_relevant" and len(not_relevant_lines) < max_per_label:
            not_relevant_lines.append(sample)
        if len(relevant_lines) >= max_per_label and len(not_relevant_lines) >= max_per_label:
            break

    relevant_block = "\n".join(relevant_lines) if relevant_lines else "- None yet"
    not_relevant_block = "\n".join(not_relevant_lines) if not_relevant_lines else "- None yet"
    return (
        "Past user feedback examples:\n"
        "Marked relevant:\n"
        f"{relevant_block}\n\n"
        "Marked not relevant:\n"
        f"{not_relevant_block}"
    )


def _build_prompt(
    calls: list[dict],
    profile_description: str,
    org_type: str | None,
    trl_range: tuple | None,
    feedback_items: list[dict] | None = None,
    focus_domains: list[str] | None = None,
) -> str:
    org_type_text = _safe_text(org_type) if org_type else "Not specified"
    trl_text = "Not specified"
    if trl_range and len(trl_range) == 2:
        trl_text = f"{trl_range[0]}-{trl_range[1]}"

    lines = []
    for idx, call in enumerate(calls):
        title = _normalize_whitespace(_safe_text(call.get("title")))
        summary = _normalize_whitespace(_safe_text(call.get("summary")))
        deadline = _normalize_whitespace(_safe_text(call.get("deadline"))) or "Unknown"
        source_keywords = ", ".join(_normalize_keywords(call.get("source_keywords"))[:10]) or "None"
        lines.append(
            f"{idx}. Title: {title}\n"
            f"   Summary: {summary}\n"
            f"   Deadline: {deadline}\n"
            f"   Source keywords: {source_keywords}"
        )

    calls_block = "\n".join(lines)
    feedback_block = _build_feedback_summary(feedback_items)
    domain_items = _normalize_domains(focus_domains)
    domain_block = ", ".join(domain_items) if domain_items else "Not specified"

    prompt = (
        "You are an expert funding-call relevance matcher.\n"
        "Score each funding call against the user profile.\n"
        "Be helpful — surface opportunities the user might miss, not just perfect matches.\n\n"
        "Scoring rules:\n"
        "- 0 = clearly irrelevant (wrong sector, wrong country, wrong org type)\n"
        "- 20-40 = loosely relevant (right org type but unclear thematic fit)\n"
        "- 40-60 = moderately relevant (matches org type AND could fit their domain/activity)\n"
        "- 60-80 = strong match (clear thematic + org type + TRL fit)\n"
        "- 80-100 = excellent match (highly specific to what they do)\n"
        "- Consider: thematic fit, sector fit, TRL fit, org type eligibility, geographic fit.\n"
        "- Calls that are broadly available to the user's org type (e.g. SME grants, innovation credits) should score at least 20-40 even without perfect domain overlap.\n"
        "- Calls in the user's language or country context get a relevance boost.\n"
        "- Use past feedback to avoid calls similar to those marked not relevant.\n\n"
        "User profile:\n"
        f"- Description: {_normalize_whitespace(profile_description)}\n"
        f"- Organisation type: {org_type_text}\n"
        f"- TRL range: {trl_text}\n\n"
        f"- Focus domains: {domain_block}\n"
        "- Focus domains help prioritise, but don't exclude calls that match the org type and general activity.\n\n"
        f"{feedback_block}\n\n"
        "Funding calls:\n"
        f"{calls_block}\n\n"
        "Return ONLY a JSON array with one object per call index.\n"
        "Format exactly:\n"
        "[{\"index\": 0, \"score\": 85, \"reason\": \"Strong match: ...\"}]\n"
        "Requirements:\n"
        "- Include every provided index exactly once.\n"
        "- score must be an integer 0-100.\n"
        "- reason must be one concise line.\n"
        "- No markdown, no extra text."
    )
    return prompt


def _extract_json_array(text: str):
    if not text:
        return None
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    match = re.search(r"\[\s*\{.*\}\s*\]", text, flags=re.DOTALL)
    if not match:
        return None
    snippet = match.group(0)
    try:
        parsed = json.loads(snippet)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        return None
    return None


async def _llm_score(
    calls: list[dict],
    profile_description: str,
    org_type: str | None,
    trl_range: tuple | None,
    api_key: str,
    feedback_items: list[dict] | None = None,
    focus_domains: list[str] | None = None,
):
    prompt = _build_prompt(
        calls,
        profile_description,
        org_type,
        trl_range,
        feedback_items=feedback_items,
        focus_domains=focus_domains,
    )

    payload = {
        "model": settings.matcher_openai_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You output strict JSON only."},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(OPENAI_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    parsed = _extract_json_array(content)
    if parsed is None:
        raise ValueError("Could not parse JSON array from LLM response")

    by_index = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        score = item.get("score")
        reason = item.get("reason")
        if not isinstance(idx, int):
            continue
        try:
            score_int = int(score)
        except Exception:
            continue
        score_int = max(0, min(100, score_int))
        reason_text = _normalize_whitespace(_safe_text(reason)) or "No reason provided"
        by_index[idx] = {"score": score_int, "reason": reason_text}

    results = []
    for idx, call in enumerate(calls):
        item = by_index.get(idx)
        if not item:
            continue
        if item["score"] < max(0, min(100, settings.matcher_min_score)):
            continue
        enriched = dict(call)
        enriched["score"] = item["score"]
        enriched["reasons"] = [item["reason"]]
        results.append(enriched)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:MAX_RESULTS]


async def _llm_score_anthropic(
    calls: list[dict],
    profile_description: str,
    org_type: str | None,
    trl_range: tuple | None,
    api_key: str,
    feedback_items: list[dict] | None = None,
    focus_domains: list[str] | None = None,
):
    prompt = _build_prompt(
        calls,
        profile_description,
        org_type,
        trl_range,
        feedback_items=feedback_items,
        focus_domains=focus_domains,
    )
    payload = {
        "model": settings.matcher_anthropic_model,
        "max_tokens": 2500,
        "temperature": 0.1,
        "system": "You output strict JSON only.",
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content_blocks = data.get("content") or []
    text_parts = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(_safe_text(block.get("text")))
    content = "\n".join(text_parts).strip()

    parsed = _extract_json_array(content)
    if parsed is None:
        raise ValueError("Could not parse JSON array from Anthropic response")

    by_index = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        score = item.get("score")
        reason = item.get("reason")
        if not isinstance(idx, int):
            continue
        try:
            score_int = int(score)
        except Exception:
            continue
        score_int = max(0, min(100, score_int))
        reason_text = _normalize_whitespace(_safe_text(reason)) or "No reason provided"
        by_index[idx] = {"score": score_int, "reason": reason_text}

    results = []
    for idx, call in enumerate(calls):
        item = by_index.get(idx)
        if not item:
            continue
        if item["score"] < max(0, min(100, settings.matcher_min_score)):
            continue
        enriched = dict(call)
        enriched["score"] = item["score"]
        enriched["reasons"] = [item["reason"]]
        results.append(enriched)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:MAX_RESULTS]


async def _score_with_provider(
    calls: list[dict],
    profile_description: str,
    org_type: str | None,
    trl_range: tuple | None,
    feedback_items: list[dict] | None = None,
    focus_domains: list[str] | None = None,
) -> list[dict]:
    provider = (settings.matcher_llm_provider or "anthropic").strip().lower()
    if provider == "anthropic":
        api_key = (settings.anthropic_api_key or "").strip()
        if not api_key:
            logger.warning("LLM scoring with anthropic selected but ANTHROPIC_API_KEY is missing")
            return []
        return await _llm_score_anthropic(
            calls,
            profile_description,
            org_type,
            trl_range,
            api_key,
            feedback_items=feedback_items,
            focus_domains=focus_domains,
        )

    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        logger.warning("LLM scoring with openai selected but OPENAI_API_KEY is missing")
        return []
    return await _llm_score(
        calls,
        profile_description,
        org_type,
        trl_range,
        api_key,
        feedback_items=feedback_items,
        focus_domains=focus_domains,
    )


async def score_calls(
    calls: list[dict],
    profile_description: str,
    org_type: str | None,
    trl_range: tuple | None,
    feedback_items: list[dict] | None = None,
    focus_domains: list[str] | None = None,
) -> list[dict]:
    if not calls:
        return []

    trimmed_calls = calls[:MAX_CALLS_IN_PROMPT]
    candidate_calls = [call for call in trimmed_calls if not _is_non_call_item(call)]
    if not candidate_calls:
        return []
    normalized_profile_description = _normalize_whitespace(profile_description)
    domain_terms = _build_domain_terms(focus_domains)
    try:
        scored = await _score_with_provider(
            candidate_calls,
            normalized_profile_description,
            org_type,
            trl_range,
            feedback_items=feedback_items,
            focus_domains=focus_domains,
        )
        if not domain_terms:
            return scored
        filtered = [call for call in scored if _passes_domain_gate(call, domain_terms)]
        return filtered[:MAX_RESULTS]
    except Exception as exc:
        logger.exception("LLM scoring failed: %s", exc)
        return []
