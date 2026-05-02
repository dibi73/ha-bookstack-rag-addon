# CLAUDE.md — ha-bookstack-rag-addon

> **Pointer-Datei.** Single-Source-of-Truth für das vollständige Briefing sind
> die obsidian-Dokumente unten. Diese Datei fasst nur das absolut Notwendige
> zusammen, damit eine frische Claude-Session sofort handlungsfähig ist.

## Pflicht-Lektüre vor jedem produktiven Schritt

1. `C:\Users\danie\Documents\obsidian\Daniel\privat\Claude_Anweisungen_bookstack_rag_addon.md`
   — Workflow-Regeln, HARD RULES, Memory-Konventionen, Stage-Plan
2. `C:\Users\danie\Documents\obsidian\Daniel\privat\Anforderungsdokument_bookstack_rag_addon.md`
   — Funktionsumfang, Architektur, Sicherheit, Roadmap, Nicht-Ziele
3. `C:\Users\danie\Documents\obsidian\Daniel\privat\Architektur_HA_BookStack_RAG.md`
   (Schicht 4) — Kontext im Gesamtsystem

## Was das Add-on tut, in einem Satz

File-Watcher auf `<config>/bookstack_export/*.md` (geschrieben von der
Schwester-Integration `ha-bookstack-sync` v0.13+) → Embedding via
`nomic-embed-text` → Qdrant-Vector-Store → RAG-Query mit OpenAI-kompatiblem
LLM-Endpoint → Web-UI über HA-Ingress.

## HARD RULES (Auszug — Begründungen im Anweisungsdokument §3)

1. **Tool-Friktionen sofort melden.** Wenn Toolchain/Workflow zickt: User
   fragen, nicht 10 Workarounds stapeln.
2. **Anforderungsdokument nach jedem Release ohne Aufforderung pflegen.**
   Pfad oben. Mindestens Header-Stand, §4 Funktionsumfang, §10 Roadmap,
   §13 Lessons Learned.
3. **In-memory ist nie Source of Truth** für persistierten Zustand.
   Embedding-Cache → Qdrant. Hashes → Qdrant-Payload. Config → `/data/options.json`.
4. **Default-off bei „kostet was"-Features.** LLM-Endpoint leer per Default,
   kein Auto-Cloud-Fallback, keine Telemetrie.
5. **Add-on schreibt nichts zurück nach HA/BookStack.** Read-only auf
   `<config>/bookstack_export/`.
6. **Reconcile-Logik in ALLEN Entry-Points.** Watcher-Event + manueller
   `/api/reindex` + Container-Restart rufen dieselbe zentrale Funktion.

## Repo-Layout (siehe Anweisungsdokument §2 für Details)

```
ha-bookstack-rag-addon/
├── repository.yaml          ← HACS-Add-on-Repository-Marker
├── .ruff.toml + pytest.ini + requirements*.txt
├── .github/workflows/       ← lint, test, build
└── bookstack-rag/           ← der eigentliche Add-on (slug: bookstack_rag)
    ├── config.yaml          ← HA-Add-on-Manifest
    ├── build.yaml           ← Multi-Arch BUILD_FROM
    ├── Dockerfile
    ├── rootfs/etc/s6-overlay/s6-rc.d/   ← s6-overlay v3 services
    ├── translations/        ← HA-Add-on-Optionen (DE/EN)
    ├── app/                 ← Python-App
    │   ├── main.py          ← FastAPI factory
    │   ├── config.py        ← /data/options.json lesen
    │   └── api.py           ← REST-Endpoints
    └── tests/
```

## Stage-Plan

- **Stage 0 (v0.1.0)**: Skelett-Repo + minimaler FastAPI-Server (`/api/status`).
- **Stage 1 (v0.2.0)**: Embedder (nomic-embed-text) + Qdrant + File-Watcher.
- **Stage 2 (v0.3.0)**: LLM-Integration (OpenAI-kompatibel, Streaming).
- **Stage 3 (v0.4.0)**: Web-UI über HA-Ingress.
- **Stage 4+**: HA-Conversation-Plattform (optional).

## Schwester-Repo (Pattern-Referenz)

`c:/dev/ha-bookstack-sync/` — Release-Workflow, ruff-Config,
Translations-Struktur, README-Stil. Wenn hier ein Pattern fehlt, dort nachschauen.

## Memory

Eigener Memory-Ordner: `C:\Users\danie\.claude\projects\c--dev-ha-bookstack-rag-addon\memory\`.
Index in `MEMORY.md` dort. Pflicht-Items beim Start einer frischen Session
vorhanden? Prüfen — falls nicht: Anweisungsdokument §4 Migration-Items anlegen.

## Sprache & Kommunikation

- **User**: deutschsprachig, Senior-Dev — direkte Sprache, Trade-Offs explizit benennen.
- **Code/Tests/Issues/Commit-Messages**: Englisch.
- **User-facing UI / Release-Notes**: Deutsch + Englisch.
- **Bei Design-Fragen**: 2-3 Sätze + konkrete Empfehlung + main Trade-off.
- **Bei Friktionen**: sofort ansprechen.
