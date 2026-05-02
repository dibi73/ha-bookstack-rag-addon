# BookStack RAG — Home Assistant Add-on

> Available in: **English** · [Deutsch](README.de.md)

A Home Assistant add-on that indexes the Markdown export produced by the
sister integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) and
makes your smart-home documentation queryable in natural language —
through any OpenAI-compatible LLM endpoint (Ollama, OpenAI, Anthropic via
proxy, …) and a simple web UI for the whole household.

## Status

**Stage 1 — v0.2.0**.

This release indexes the BookStack export and answers natural-language
queries with the top-K matching documents. LLM integration (Stage 2)
and the web UI (Stage 3) follow.

What ships:
- File watcher on `<config>/bookstack_export/` with idempotent
  hash-keyed indexing, soft-delete on removal.
- Local embedding via `nomic-ai/nomic-embed-text-v1.5` (CPU-only,
  pre-baked into the image).
- Qdrant sidecar container (in-process, persistence at `/data/qdrant/`).
- `POST /api/query {text, top_k?}` returns ranked hits with
  `bookstack_page_id` so the caller can link back to the originating
  BookStack page.
- `POST /api/reindex` triggers a manual reconcile sweep.

> ⚠️ **v0.2.0 drops armv7.** Stage 1 pulls in PyTorch transitively;
> PyTorch ships no armv7 wheels. Pi 4 owners on **32-bit Raspberry
> Pi OS** need to switch to a 64-bit OS image — same hardware,
> different OS. amd64 (x86 NAS, Homelab) and aarch64 (Pi 4 64-bit,
> newer ARM NAS) remain fully supported.

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

## Configuration

| Option | Default | Description |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Path inside the container where the Markdown export lives. |
| `embedding_model` | `nomic-ai/nomic-embed-text-v1.5` | sentence-transformers model used for embeddings. The default is pre-baked into the image; pointing this elsewhere triggers a one-time download. |
| `top_k` | `5` | Default number of `/api/query` hits when the caller does not pass an explicit `top_k`. |

LLM-endpoint options (`llm_base_url`, `llm_api_key`, `llm_model`) appear
in v0.3.0. Until then the add-on returns matching documents but no
synthesised answer.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | `{status, export_path, markdown_files, indexed}` — readiness + counts. |
| `POST` | `/api/query` | Body: `{text: "...", top_k?: 1-50}`. Returns `{query, top_k, hits: [{doc_id, score, title, content_preview, bookstack_page_id}]}`. |
| `POST` | `/api/reindex` | Run a full reconcile sweep. Returns `{indexed, unchanged, skipped, failed, total}`. |

All endpoints are reachable through the HA Ingress panel.

## Roadmap

- [x] **Stage 0 (v0.1.0)** — skeleton add-on, CI, status endpoint.
- [x] **Stage 1 (v0.2.0)** — file watcher, embedding (nomic-embed-text),
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
| Raspberry Pi 4 (4 GB, **64-bit OS**) | ✅ embedding works (slow); LLM should be remote |
| Synology / x86 NAS | ✅ embedding fine; small local LLM possible |
| Local PC with GPU | ✅ run Ollama there, point the add-on at it |
| Pi 4 (32-bit OS) or Pi 3 | ❌ since v0.2.0: armv7 is no longer supported (no PyTorch wheels) |
| Pi 4 (2 GB) | ⚠️ marginal — embedding model alone needs ~500 MB |

Minimum RAM for the add-on itself (without LLM): ~1 GB. Supported architectures: **amd64**, **aarch64** (so Pi 4/5 must run a 64-bit OS).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Lint and tests must be green;
new behaviour needs tests.

## Sister project

[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) — the
HACS integration that produces the Markdown export this add-on consumes.
Both projects evolve independently; you need both for the full system.

## License

MIT — see [LICENSE](LICENSE).
