# BookStack RAG — Documentation

This page is rendered inside the Home Assistant Add-on UI.

> ⏱️ **Erstinstallation dauert 5-15 Minuten.** Der HA-Supervisor baut den
> Container lokal auf deinem Host: `python:3.12-slim-bookworm`-Base
> ziehen, ~700 MB PyTorch installieren, das `nomic-embed-text`-Modell
> (~500 MB) vorab herunterladen, das Qdrant-Binary kopieren. Während
> dieser Zeit zeigt HA *„Installing…"* — das ist normal, nicht hängen.
> Folgende Updates und Container-Restarts sind viel schneller (Layer-
> Cache + Modell ist im Image gebaked). Erstinstall braucht ~3 GB freie
> Disk und ~2 GB freien RAM auf dem HA-Host.

## What this add-on does

It indexes the Markdown export produced by the sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes that documentation queryable in natural language. Optionally it
forwards retrieval hits as context to an OpenAI-compatible LLM endpoint
and streams the synthesised answer back.

The full pipeline:

1. **Watch** `<config>/bookstack_export/*.md` for changes (file-system
   events, debounced 500 ms).
2. **Embed** each Markdown file with a local embedding model
   (`nomic-ai/nomic-embed-text-v1.5`, 768 dimensions, CPU-only).
3. **Store** vectors plus YAML-frontmatter metadata in an embedded
   Qdrant sidecar with persistent disk storage at `/data/qdrant/`.
4. **Retrieve** the top-K matches for a user question (cosine search,
   tombstoned documents excluded).
5. **Synthesise** an answer via a configured OpenAI-compatible LLM
   endpoint, with prompt-injection-defended context wrapping
   (`<doc>` marker tags). Optional multi-turn chat history is persisted
   in SQLite at `/data/conversations.db`.

## Current stage

**Stage 3 — v0.4.0.** Built-in web UI is now mounted at the add-on's
ingress panel root: open *Settings → Add-ons → BookStack RAG →
Open Web UI* and you land in a full chat interface (sidebar with chat
history, streaming Markdown answers, mobile-responsive). REST endpoints
remain available for programmatic access.

> 64-bit OS required since v0.2.0. PyTorch (transitive via
> `sentence-transformers`) ships no armv7 wheels.

## Configuration options

### Indexing options (defaults work for most setups)

#### `bookstack_export_path`

- **Type**: `str` · **Default**: `/config/bookstack_export`
- Path inside the container where the Markdown export lives.

#### `embedding_model`

- **Type**: `str?` · **Default**: `nomic-ai/nomic-embed-text-v1.5`
- sentence-transformers model. Default is pre-baked into the image.

#### `top_k`

- **Type**: `int(1,50)?` · **Default**: `5`
- How many retrieval hits `/api/query` returns by default.

### LLM options (LLM stays disabled until at least `llm_base_url` and `llm_model` are set)

#### `llm_base_url`

- **Type**: `str?` · **Default**: empty
- OpenAI-compatible chat-completions root URL.

#### `llm_api_key`

- **Type**: `password?` · **Default**: empty
- Bearer token. HA hides it in the UI; the add-on never logs it.

#### `llm_model`

- **Type**: `str?` · **Default**: empty
- Model identifier as the endpoint expects it.

#### `llm_timeout`

- **Type**: `int(5,600)?` · **Default**: `60`
- Per-request timeout in seconds.

#### `max_turns`

- **Type**: `int(1,200)?` · **Default**: `20`
- Conversation-history truncation: only the last N user/assistant
  pairs reach the LLM.

#### `system_prompt`

- **Type**: `str?` · **Default**: empty (built-in bilingual prompt is used)
- Override for the system message.

### Source-link options (off by default)

#### `bookstack_base_url`

- **Type**: `url?` · **Default**: empty
- Public URL of your BookStack instance. When set together with
  `bookstack_page_id` in the document's frontmatter, each context
  block in the LLM prompt gets a `[BookStack](.../link/<page-id>)`
  citation the LLM can cite. The link uses BookStack's permalink
  endpoint, so it survives page-slug renames.

#### `homeassistant_base_url`

- **Type**: `url?` · **Default**: empty
- Public URL of your Home Assistant instance. Combined with
  `ha_object_kind` + `ha_object_id` from the frontmatter, each
  context block gets an `[HA Gerät](.../config/devices/device/<id>)`
  (or the matching automation/area/scene/script/integration/entity/
  helper) citation. The LLM is instructed to cite these links
  sparingly so the user can jump to the device-edit page directly
  from the answer.

## LLM endpoint examples

### Ollama on a LAN host (recommended)

```yaml
llm_base_url: http://192.168.1.100:11434/v1
llm_api_key: ""
llm_model: qwen2.5:7b
```

Free, local, private. Run Ollama on a machine with a GPU; point the
add-on at it over the LAN.

### OpenAI

```yaml
llm_base_url: https://api.openai.com/v1
llm_api_key: sk-...
llm_model: gpt-4o-mini
```

### Anthropic (OpenAI-compat layer)

```yaml
llm_base_url: https://api.anthropic.com/v1
llm_api_key: sk-ant-...
llm_model: claude-haiku-4-5
```

### Google Gemini (OpenAI-compat endpoint)

```yaml
llm_base_url: https://generativelanguage.googleapis.com/v1beta/openai
llm_api_key: AIza...
llm_model: gemini-2.0-flash
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Readiness + counts + `llm_configured` flag. |
| `POST` | `/api/query` | Embed query, retrieve hits, optionally synthesise answer. |
| `POST` | `/api/reindex` | Full reconcile sweep. |
| `GET` | `/api/conversations` | Summaries (id, title preview, message count, timestamps). |
| `GET` | `/api/conversations/{id}` | Full message history. |
| `DELETE` | `/api/conversations/{id}` | Hard-delete a conversation. |

### `/api/query` request body

```json
{
  "text": "Was macht der Bewegungsmelder am Gang?",
  "top_k": 3,
  "conversation_id": "<uuid-from-prior-response>",
  "stream": true
}
```

- `text` — required, ≥ 1 character.
- `top_k` — optional override of the default config value (1–50).
- `conversation_id` — optional. Omit for a fresh chat; include the id
  returned by the previous response to continue.
- `stream` — optional. `true` switches the response from JSON to SSE.

### Modes

1. **Retrieval-only** (no LLM configured, no `stream`, no
   `conversation_id`): returns `{query, top_k, hits}` exactly like
   v0.2.0.
2. **One-shot LLM answer** (LLM configured, `stream: false`): returns
   `{query, top_k, hits, conversation_id, answer}`.
3. **Streaming SSE** (`stream: true`): emits

   ```
   event: hit
   data: {...}

   event: delta
   data: {"content": "..."}

   event: done
   data: {"conversation_id": "..."}
   ```

   Browser clients can use `EventSource`; `curl -N` works too.

`stream: true` and `conversation_id` both require an LLM to be
configured — the endpoint returns 503 otherwise.

## Permissions

- `map: - config:ro` — read-only access to your HA `config/` folder.
- The Qdrant sidecar binds to `127.0.0.1` only.
- `auth_api: false` — the add-on does not call the HA API.

## Persistence

- Qdrant: `/data/qdrant/storage/` (vector index, payloads).
- Conversations: `/data/conversations.db` (SQLite).
- Both survive add-on restarts and updates.

## Logs

*Settings → Add-ons → BookStack RAG → Log* shows interleaved output
from the qdrant and api services.

## Troubleshooting

**`/api/query` returns 503** — embedder or Qdrant index not ready yet.
Wait ~10 s after first start; retry.

**LLM returns 401 / 403** — wrong API key or wrong model identifier
for the provider. Double-check the configuration; `llm_api_key` is
masked in the UI but the live value is what's sent.

**Streaming hangs** — most often the upstream endpoint isn't actually
streaming. For Ollama, ensure the model is loaded
(`ollama run <model>`) before the first query so cold-load doesn't
trigger the timeout.

**Conversation context grows too large for the LLM** — lower
`max_turns` or shorten `system_prompt`. The add-on truncates
conversation history before sending; long histories are not the cause
unless `max_turns` is also large.

## Source

Source code, issue tracker, contributing guide:
<https://github.com/dibi73/ha-bookstack-rag-addon>.
