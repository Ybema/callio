# Watch to Prepare Data Contract

This contract defines how `watch/` hands a discovered call to `framework/`.

## Target Workspace

For a source slug `<source-slug>` and call slug `<call-slug>`, the framework workspace is:

`framework/calls/<source-slug>/<call-slug>/`

Backward compatibility:

- Existing flat workspaces (`framework/calls/<call-slug>/`) are still supported by framework path resolution.

Required directories:

- `framework/calls/<source-slug>/<call-slug>/input/call_documents/`
- `framework/calls/<source-slug>/<call-slug>/input/lfa_documents/`
- `framework/calls/<source-slug>/<call-slug>/input/strategy_documents/`
- `framework/calls/<source-slug>/<call-slug>/input/work_packages/`

## Minimum Payload from Watch

Watch should provide at least:

- `call_slug` (kebab-case identifier)
- `source_url` (canonical call URL)
- `title`
- `deadline` (ISO date if available)
- `summary`

## Metadata Handoff v1 (Implemented)

Current integration writes metadata-only manifests from Watch to:

- `framework/calls/<source-slug>/<call-slug>/input/call_documents/<source>_<timestamp>_watch_manifest.json`

Payload schema:

```json
{
  "call_slug": "string",
  "source_slug": "string",
  "source_url": "string",
  "title": "string",
  "url": "string",
  "deadline": "string|null",
  "summary": "string|null",
  "call_hash": "string|null",
  "source_id": "string",
  "source_label": "string",
  "seen_at": "ISO-8601 datetime"
}
```

Idempotency rule:

- Watch writes and checks `framework/calls/<source-slug>/<call-slug>/output/watch_handoff/index.json`
- If `call_hash` (or fallback dedupe key) already exists in index, the manifest is skipped

## File Delivery Rules

If Watch downloads source files, it should place them in:

- `framework/calls/<source-slug>/<call-slug>/input/call_documents/`

Naming convention:

- Prefix with source and date where possible
- Use ASCII filenames
- Keep original extension when available

Example:

- `tenderned_2026-03-06_notice.pdf`
- `esa_2026-03-06_guidelines.docx`

## Lifecycle Ownership

- Watch owns discovery and raw document intake.
- Framework owns extraction, restructuring, review scoring, and outputs.
- Framework output is written under `framework/calls/<source-slug>/<call-slug>/output/`.

## Prepare Endpoint Contract

When a user selects a call in Watch and triggers prepare:

- Endpoint: `POST /calls/{seen_call_id}/prepare`
- Behavior:
  - Ensure workspace exists under `framework/calls/<source-slug>/<call-slug>/`
  - Write/update watch metadata handoff
  - Discover and download call documents into `input/call_documents/`

Response shape:

```json
{
  "status": "ok",
  "workspace_path": "string",
  "call_slug": "string",
  "source_slug": "string",
  "handoff": { "created": 0, "skipped": 0, "errors": 0 },
  "documents": [
    {
      "url": "string",
      "filename": "string|null",
      "size_bytes": "number|null",
      "status": "downloaded|error",
      "error": "string|null"
    }
  ],
  "documents_downloaded": 0,
  "documents_errors": 0
}
```
