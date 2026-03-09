# LLM Provider

## Provider Chain

`scripts/review_engine/llm_provider.py` manages LLM access with automatic fallback.

**Default order:** OpenAI → Cursor CLI

```
LLMProvider(preferred_provider="openai")
    │
    ├─ Try OpenAI API (chat.completions, json_object mode)
    │   ├─ Success → return with cost tracking
    │   └─ Fail → try Cursor CLI
    │
    └─ Try Cursor CLI (cursor agent --print --output-format=json)
        ├─ Success → return (cost = $0)
        └─ Fail → error
```

If the preferred provider is set to `"cursor"`, the order reverses.

## Why OpenAI Is Default

The provider was originally set to prefer Cursor CLI. On the SSH deployment server, `cursor status` succeeds (making the availability check pass), but `cursor agent` hangs because there is no interactive IDE session backing it. Each hang lasts 180 seconds — with 3 blocks per Phase A run, that adds ~9 minutes of dead time before fallback.

Changed 2026-03-03: default switched to `"openai"` in both `llm_provider.py` (class default) and `review_engine.py` (call site).

## Availability Checks

| Provider | Check | Limitation |
|----------|-------|------------|
| Cursor CLI | `cursor status` (5s timeout) | Returns true even when `cursor agent` can't work (SSH, headless) |
| OpenAI | `OpenAI()` constructor succeeds | Requires `OPENAI_API_KEY` in environment — needs `load_dotenv()` |

## Model Mapping

When Cursor CLI is used, OpenAI model names are mapped:

| Requested Model | Cursor Model |
|-----------------|--------------|
| gpt-4o-mini | sonnet-4 |
| gpt-4o | sonnet-4 |
| gpt-3.5-turbo | sonnet-4 |

## Cost Tracking

OpenAI calls track actual token usage and calculate cost per model:

| Model | Input ($/1K) | Output ($/1K) |
|-------|-------------|---------------|
| gpt-4o-mini | $0.00015 | $0.0006 |
| gpt-3.5-turbo | $0.0015 | $0.002 |
| gpt-4o | $0.005 | $0.015 |

Cursor CLI calls are tracked with estimated token counts and $0 cost.

Results are accumulated in `meta.cost_tracking` in the review output:
```json
{
  "total_cost_usd": 0.008,
  "total_tokens": 12500,
  "api_calls": 3,
  "provider_usage": { "openai": 3 }
}
```

## JSON Response Handling

Both providers are instructed to return JSON. The engine handles:
- Clean JSON responses (parsed directly)
- Markdown-wrapped JSON (```json ... ``` blocks stripped)
- Conversational responses with embedded JSON (regex extraction)
- Complete failures (OpenAI fallback attempted from within the Cursor response handler)
