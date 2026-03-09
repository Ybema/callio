#!/usr/bin/env python3
"""Interactive human-in-the-loop discussion engine for Phase A iteration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from jinja2 import Template

from scripts.word_export import convert_markdown_to_word


ChunkCallback = Optional[Callable[[str], None]]


@dataclass
class LoadedContext:
    structured_lfa_path: Path
    derivation_path: Optional[Path]
    structural_review_path: Optional[Path]
    alignment_review_path: Optional[Path]
    improvement_guide_path: Optional[Path]
    call_context_path: Optional[Path]
    team_notes_path: Optional[Path]
    structured_lfa_text: str
    derivation_text: str
    structural_review_text: str
    alignment_review_text: str
    improvement_guide_text: str
    call_context_text: str
    team_notes_text: str


def _read_text(path: Optional[Path], max_chars: int = 0) -> str:
    if not path or not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text


def _latest_file(base_dir: Path, pattern: str) -> Optional[Path]:
    matches = sorted(base_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _review_json_to_markdown(path: Optional[Path], max_fixes: int = 2) -> str:
    if not path or not path.exists():
        return "[No review file found]"
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return _read_text(path, max_chars=8000)

    lines: List[str] = []
    meta = payload.get("meta", {})
    scores = payload.get("scores", {})
    findings = payload.get("findings", {})

    lines.append(f"Review file: `{path.name}`")
    if meta:
        lines.append(f"- Review type: {meta.get('review_type', 'unknown')}")
        lines.append(f"- Model: {meta.get('model', 'unknown')}")
        lines.append(f"- Generated: {meta.get('timestamp', 'unknown')}")
    if scores:
        total = scores.get("total_score")
        band = scores.get("band")
        if total is not None:
            lines.append(f"- Total score: {total}")
        if band:
            lines.append(f"- Band: {band}")
    lines.append("")
    lines.append("## Findings summary")

    for code, data in findings.items():
        lines.append(f"### {code}")
        gaps = data.get("gaps") or []
        fixes = data.get("fixes") or []
        suggested_text = data.get("suggested_text") or []
        if gaps:
            lines.append(f"- Gap: {gaps[0]}")
        if fixes:
            for fix in fixes[:max_fixes]:
                lines.append(f"- Fix: {fix}")
        if suggested_text:
            lines.append(f"- Suggested text: {suggested_text[0]}")
        lines.append("")

    return "\n".join(lines).strip()


class DiscussionSession:
    """Coordinator for context loading, chat loop helpers, and finalization."""

    def __init__(
        self,
        framework_root: Path,
        call_dir: Path,
        call_slug: str,
        model: str,
        resume: Optional[Path] = None,
    ):
        self.framework_root = framework_root
        self.call_dir = call_dir
        self.call_slug = call_slug
        self.model = model
        self.started_at = datetime.now()
        self.messages: List[Dict[str, str]] = []
        self.current_draft: str = ""
        self.finalized = False

        self.output_root = self.call_dir / "output" / "discussions"
        self.output_root.mkdir(parents=True, exist_ok=True)
        if resume:
            self.session_dir = resume
            self._load_resume_state()
        else:
            stamp = self.started_at.strftime("%Y%m%d_%H%M%S")
            self.session_dir = self.output_root / f"session_{stamp}"
            self.session_dir.mkdir(parents=True, exist_ok=True)

        self.context = self._load_context()
        self.system_prompt = self._render_system_prompt()

    def _load_context(self) -> LoadedContext:
        output_dir = self.call_dir / "output"
        phase_a = output_dir / "phase_a"
        pre_phase_context = output_dir / "pre_phase" / "context"

        structured_lfa = phase_a / "lfa_restructured" / "lfa_structured.md"
        if not structured_lfa.exists():
            fallback = _latest_file(self.call_dir / "input" / "lfa_documents", "*_processed_*.md")
            if not fallback:
                raise FileNotFoundError(
                    f"No structured LFA or processed LFA found in {self.call_dir / 'input' / 'lfa_documents'}"
                )
            structured_lfa = fallback

        derivation = phase_a / "lfa_restructured" / "lfa_derivation.md"
        structural_review = _latest_file(phase_a / "review_results" / "structural", "*.json")
        alignment_review = _latest_file(phase_a / "review_results" / "alignment", "*.json")

        improvement_guide = phase_a / "improvement_guide.md"
        improvement_guide_path = improvement_guide if improvement_guide.exists() else None

        call_context = None
        for pattern in ["call_context_compiled_*.md", "summary.md", "skill_test_sonnet.md"]:
            call_context = _latest_file(pre_phase_context, pattern)
            if call_context:
                break

        team_notes = self.call_dir / "input" / "team_notes.md"
        team_notes_path = team_notes if team_notes.exists() else None

        return LoadedContext(
            structured_lfa_path=structured_lfa,
            derivation_path=derivation if derivation.exists() else None,
            structural_review_path=structural_review,
            alignment_review_path=alignment_review,
            improvement_guide_path=improvement_guide_path,
            call_context_path=call_context,
            team_notes_path=team_notes_path,
            structured_lfa_text=_read_text(structured_lfa, max_chars=120000),
            derivation_text=_read_text(derivation if derivation.exists() else None, max_chars=50000),
            structural_review_text=_review_json_to_markdown(structural_review),
            alignment_review_text=_review_json_to_markdown(alignment_review),
            improvement_guide_text=_read_text(improvement_guide_path, max_chars=80000),
            call_context_text=_read_text(call_context, max_chars=50000),
            team_notes_text=_read_text(team_notes_path, max_chars=20000),
        )

    def _render_system_prompt(self) -> str:
        template_path = self.framework_root / "templates" / "discussion" / "system_prompt.md"
        template = Template(template_path.read_text(encoding="utf-8", errors="ignore"))
        return template.render(
            call_slug=self.call_slug,
            model=self.model,
            started_at=self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            structured_lfa=self.context.structured_lfa_text,
            derivation=self.context.derivation_text or "[No derivation file found]",
            improvement_guide=self.context.improvement_guide_text,
            structural_review=self.context.structural_review_text,
            alignment_review=self.context.alignment_review_text,
            call_context=self.context.call_context_text or "[No call context found]",
            team_notes=self.context.team_notes_text,
        )

    def _anthropic_client(self):
        import anthropic

        return anthropic.Anthropic()

    def _call_llm(
        self,
        user_text: str,
        on_chunk: ChunkCallback = None,
        temperature: float = 0.2,
    ) -> str:
        user_payload = {"role": "user", "content": user_text}
        request_messages = self.messages + [user_payload]

        client = self._anthropic_client()
        chunks: List[str] = []
        with client.messages.stream(
            model=self.model,
            max_tokens=32000,
            system=self.system_prompt,
            messages=request_messages,
            temperature=temperature,
        ) as stream:
            for chunk in stream.text_stream:
                chunks.append(chunk)
                if on_chunk:
                    on_chunk(chunk)
            stream.get_final_message()

        assistant_text = "".join(chunks).strip()
        self.messages.append(user_payload)
        self.messages.append({"role": "assistant", "content": assistant_text})
        return assistant_text

    def handle_message(self, text: str, on_chunk: ChunkCallback = None) -> str:
        return self._call_llm(text, on_chunk=on_chunk, temperature=0.2)

    def command_help(self) -> str:
        return (
            "Commands:\n"
            "  /help                 Show commands\n"
            "  /show <section>       Show loaded context section (lfa, derivation, guide, structural, alignment, call, team)\n"
            "  /guide                Show the improvement guide (section-oriented feedback)\n"
            "  /team                 Show loaded team notes\n"
            "  /draft                Generate current improved LFA draft\n"
            "  /diff                 Show diff between baseline and current draft\n"
            "  /save                 Save checkpoint files\n"
            "  /finalize             Create final outputs and end session"
        )

    def show_section(self, section: str) -> str:
        section = section.strip().lower()
        mapping = {
            "lfa": self.context.structured_lfa_text,
            "derivation": self.context.derivation_text or "[No derivation file found]",
            "guide": self.context.improvement_guide_text or "[No improvement guide found]",
            "structural": self.context.structural_review_text,
            "alignment": self.context.alignment_review_text,
            "call": self.context.call_context_text or "[No call context found]",
            "team": self.context.team_notes_text or "[No team notes found at input/team_notes.md]",
        }
        if section not in mapping:
            return "Unknown section. Use one of: lfa, derivation, guide, structural, alignment, call, team"
        return mapping[section]

    def draft(self, on_chunk: ChunkCallback = None) -> str:
        prompt = (
            "Using this full discussion so far, produce a complete improved LFA markdown document.\n"
            "Rules:\n"
            "- Output only markdown content for the improved LFA.\n"
            "- Keep a clear LFA structure.\n"
            "- Make improvements tied to review gaps and call alignment.\n"
            "- If data is missing, leave explicit placeholders rather than inventing facts."
        )
        raw = self._call_llm(prompt, on_chunk=on_chunk, temperature=0.1)
        self.current_draft = _strip_fences(raw)
        self._write_checkpoint(include_draft=True)
        return self.current_draft

    def diff(self) -> str:
        if not self.current_draft:
            return "No current draft. Run /draft first."
        before = self.context.structured_lfa_text.splitlines()
        after = self.current_draft.splitlines()
        diff_lines = list(
            unified_diff(
                before,
                after,
                fromfile="baseline_lfa.md",
                tofile="current_draft.md",
                lineterm="",
            )
        )
        if not diff_lines:
            return "No differences detected."
        return "\n".join(diff_lines[:800])

    def finalize(self, on_chunk: ChunkCallback = None) -> Dict[str, str]:
        improved_lfa = self.current_draft or self.draft(on_chunk=on_chunk)

        summary_prompt = (
            "Create a concise change summary for the team.\n"
            "Include sections: 1) What changed, 2) Why it changed, 3) Remaining open points.\n"
            "Use markdown with bullet points.\n\n"
            f"Original baseline LFA:\n{self.context.structured_lfa_text[:60000]}\n\n"
            f"Improved LFA:\n{improved_lfa[:60000]}"
        )
        change_summary = self._call_llm(summary_prompt, on_chunk=None, temperature=0.1)
        change_summary = _strip_fences(change_summary)

        improved_md_path = self.session_dir / "improved_lfa.md"
        improved_docx_path = self.session_dir / "improved_lfa.docx"
        summary_path = self.session_dir / "change_summary.md"
        transcript_path = self.session_dir / "transcript.md"
        history_path = self.session_dir / "session_history.json"
        meta_path = self.session_dir / "session_meta.json"

        improved_md_path.write_text(improved_lfa.strip() + "\n", encoding="utf-8")
        summary_path.write_text(change_summary.strip() + "\n", encoding="utf-8")
        transcript_path.write_text(self._build_transcript_markdown(), encoding="utf-8")
        history_path.write_text(json.dumps(self.messages, indent=2, ensure_ascii=False), encoding="utf-8")

        # Keep word-export config paths working by running conversion from framework root.
        prev_cwd = Path.cwd()
        try:
            os.chdir(self.framework_root)
            docx_out = convert_markdown_to_word(
                str(improved_md_path),
                output_dir=str(self.session_dir),
                filename_base="improved_lfa",
            )
        finally:
            os.chdir(prev_cwd)
        if docx_out and Path(docx_out).exists():
            generated_docx = Path(docx_out)
            if generated_docx.resolve() != improved_docx_path.resolve():
                generated_docx.replace(improved_docx_path)

        input_dir = self.call_dir / "input" / "lfa_documents"
        input_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        next_input_path = input_dir / f"improved_lfa_processed_{stamp}.md"
        next_input_path.write_text(improved_lfa.strip() + "\n", encoding="utf-8")

        meta = {
            "call_slug": self.call_slug,
            "model": self.model,
            "started_at": self.started_at.isoformat(),
            "finalized_at": datetime.now().isoformat(),
            "inputs": {
                "structured_lfa": str(self.context.structured_lfa_path),
                "derivation": str(self.context.derivation_path) if self.context.derivation_path else None,
                "structural_review": str(self.context.structural_review_path) if self.context.structural_review_path else None,
                "alignment_review": str(self.context.alignment_review_path) if self.context.alignment_review_path else None,
                "call_context": str(self.context.call_context_path) if self.context.call_context_path else None,
                "team_notes": str(self.context.team_notes_path) if self.context.team_notes_path else None,
            },
            "outputs": {
                "improved_lfa_md": str(improved_md_path),
                "improved_lfa_docx": str(improved_docx_path),
                "transcript_md": str(transcript_path),
                "change_summary_md": str(summary_path),
                "session_history_json": str(history_path),
                "next_iteration_input_md": str(next_input_path),
            },
        }
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self.finalized = True
        return {
            "improved_lfa_md": str(improved_md_path),
            "improved_lfa_docx": str(improved_docx_path),
            "transcript_md": str(transcript_path),
            "change_summary_md": str(summary_path),
            "session_meta_json": str(meta_path),
            "next_iteration_input_md": str(next_input_path),
        }

    def save(self) -> str:
        self._write_checkpoint(include_draft=bool(self.current_draft))
        return f"Checkpoint saved in {self.session_dir}"

    def _write_checkpoint(self, include_draft: bool = False) -> None:
        transcript_path = self.session_dir / "transcript.md"
        history_path = self.session_dir / "session_history.json"
        transcript_path.write_text(self._build_transcript_markdown(), encoding="utf-8")
        history_path.write_text(json.dumps(self.messages, indent=2, ensure_ascii=False), encoding="utf-8")
        if include_draft:
            draft_path = self.session_dir / "draft_lfa.md"
            draft_path.write_text(self.current_draft.strip() + "\n", encoding="utf-8")

    def _build_transcript_markdown(self) -> str:
        lines = [
            "# Discussion Transcript",
            "",
            f"- Call: `{self.call_slug}`",
            f"- Model: `{self.model}`",
            f"- Started: {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for msg in self.messages:
            role = msg.get("role", "unknown")
            lines.append(f"## {role.title()}")
            lines.append("")
            lines.append(msg.get("content", "").strip())
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _load_resume_state(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        history_path = self.session_dir / "session_history.json"
        draft_path = self.session_dir / "draft_lfa.md"
        if history_path.exists():
            self.messages = json.loads(history_path.read_text(encoding="utf-8", errors="ignore"))
        if draft_path.exists():
            self.current_draft = draft_path.read_text(encoding="utf-8", errors="ignore")

    def context_summary(self) -> str:
        lines = [
            "Loaded context:",
            f"- Structured LFA: {self.context.structured_lfa_path}",
            f"- Derivation: {self.context.derivation_path if self.context.derivation_path else 'not found'}",
            f"- Improvement guide: {self.context.improvement_guide_path if self.context.improvement_guide_path else 'not found (run Phase A first)'}",
            f"- Structural review: {self.context.structural_review_path if self.context.structural_review_path else 'not found'}",
            f"- Alignment review: {self.context.alignment_review_path if self.context.alignment_review_path else 'not found'}",
            f"- Call context: {self.context.call_context_path if self.context.call_context_path else 'not found'}",
            f"- Team notes: {self.context.team_notes_path if self.context.team_notes_path else 'not found (optional: input/team_notes.md)'}",
            f"- Session dir: {self.session_dir}",
        ]
        return "\n".join(lines)
