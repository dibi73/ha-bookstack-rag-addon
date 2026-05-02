# BookStack RAG — Home Assistant Add-on

> Available in: **English** · [Deutsch](README.de.md)

A Home Assistant add-on that indexes the Markdown export produced by the
sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes your smart-home documentation queryable in natural language —
through any OpenAI-compatible LLM endpoint (Ollama, OpenAI, Anthropic via
proxy, …) and a simple web UI for the whole household.

## Status

**Stage 0 — v0.1.0** (skeleton release).

This release ships:
- The HACS add-on repository structure.
- A minimal FastAPI server that, once installed, reports how many `.md`
  files it can see under the configured BookStack export path.
- The CI scaffolding (ruff lint, pytest, container build) for everything
  that comes next.

Indexing, embedding, RAG and the web UI come in v0.2.0+ — see the
[stage plan](#roadmap).

## How the pieces fit together

```
ha-bookstack-sync (HACS integration, separate repo)
        │
        │  writes Markdown export to <config>/bookstack_export/
        ▼
THIS ADD-ON
        │
        │  watches the export, embeds it locally (nomic-embed-text),
        │  stores vectors in an embedded Qdrant instance,
        │  forwards user queries to a configured OpenAI-compatible LLM
        ▼
Web UI through Home Assistant Ingress
```

## Installation (HACS, recommended)

1. **Settings → Add-ons → Add-on Store → ⋮ (top-right) → Repositories**
2. Paste `https://github.com/dibi73/ha-bookstack-rag-addon` and click **Add**.
3. The "BookStack RAG" add-on now appears in the store. Click **Install**.
4. Configure the export path (default: `/config/bookstack_export`, which
   matches the integration's default).
5. **Start** the add-on. The Ingress panel link appears in the HA sidebar.

## Configuration (Stage 0)

| Option | Default | Description |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Path inside the container where the Markdown export lives. The default works if you use `ha-bookstack-sync` with its default export path. |

More options will appear in later stages (LLM endpoint, model name,
top-k, etc.). They're documented in `bookstack-rag/DOCS.md`.

## Endpoints (Stage 0)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/status` | `{"status": "ok", "export_path": ..., "markdown_files": N}` |

Reachable through the HA Ingress panel.

## Roadmap

- [x] **Stage 0 (v0.1.0)** — skeleton add-on, CI, status endpoint.
- [ ] **Stage 1 (v0.2.0)** — file watcher, embedding (nomic-embed-text),
  Qdrant index, `/api/query` returning top-k documents.
- [ ] **Stage 2 (v0.3.0)** — LLM integration (OpenAI-compatible endpoint
  configurable, streaming responses).
- [ ] **Stage 3 (v0.4.0)** — Web UI: input field, answer display, source
  links back to BookStack pages.
- [ ] **Stage 4+** — HA Conversation platform integration (voice
  control), multi-LLM routing, source re-ranking.

## Non-goals

- **No write-back to HA or BookStack.** This add-on is a read-only
  consumer of the Markdown export. Documentation lives in BookStack
  (managed by the sister integration); the add-on never modifies it.
- **No own LLM server.** You bring your own LLM endpoint (local Ollama,
  cloud API, …). The add-on configures, it doesn't host.
- **No multi-tenant / multi-user system.** One household, one
  installation.

## Hardware & requirements

| Setup | Verdict |
|---|---|
| Raspberry Pi 4 (4 GB) | ✅ embedding works (slow); LLM should be remote |
| Synology / x86 NAS | ✅ embedding fine; small local LLM possible |
| Local PC with GPU | ✅ run Ollama there, point the add-on at it |
| Pi 4 (2 GB) or Pi 3 | ❌ embedding model alone exceeds available RAM |

Minimum RAM for the add-on itself (without LLM): ~1 GB.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Lint and tests must be green;
new behaviour needs tests.

## Sister project

[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) — the
HACS integration that produces the Markdown export this add-on consumes.
Both projects evolve independently; you need both for the full system.

## License

MIT — see [LICENSE](LICENSE).
