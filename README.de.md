# BookStack RAG — Home-Assistant-Add-on

> Verfügbar auf: [English](README.md) · **Deutsch**

Ein Home-Assistant-Add-on, das den Markdown-Export der Schwester-Integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) lokal
indexiert und die Smart-Home-Doku per natürlicher Sprache abfragbar macht —
über einen frei konfigurierbaren OpenAI-kompatiblen LLM-Endpoint (Ollama,
OpenAI, Anthropic via Proxy, …) und eine einfache Web-UI für die ganze
Familie.

## Status

**Stage 2 — v0.3.0**.

Das Add-on synthetisiert jetzt Antworten in natürlicher Sprache über
einen frei wählbaren OpenAI-kompatiblen LLM-Endpoint (Ollama, OpenAI,
Anthropic, Gemini, self-hosted vLLM/LM Studio). Multi-Turn-Chats werden
persistiert, Streaming-Antworten via SSE ermöglichen Live-Token-Anzeige
in einer kommenden Web-UI.

Was ausgeliefert wird:
- Alles aus v0.2.0 (File-Watcher, lokales Embedding, Qdrant-Sidecar,
  `/api/reindex`).
- `POST /api/query` erweitert um `conversation_id` (Multi-Turn) und
  `stream: true` (SSE).
- Conversation-Persistenz in SQLite unter `/data/conversations.db`.
- Neue Endpoints: `GET/DELETE /api/conversations[/{id}]`.
- LLM ist **per Default aus** — `llm_base_url` und `llm_model` setzen
  zum Aktivieren. Ohne diese bleibt das Add-on im v0.2.0-Retrieval-only-Modus.

> 64-Bit-OS-Pflicht seit v0.2.0 (kein armv7 / 32-Bit-Pi-OS — PyTorch
> hat keine armv7-Wheels).

## Wie die Teile zusammenspielen

```
ha-bookstack-sync (HACS-Integration, eigenes Repo)
        │
        │  schreibt Markdown-Export nach <config>/bookstack_export/
        ▼
DIESES ADD-ON
        │
        │  überwacht den Export, embedded lokal (nomic-embed-text),
        │  speichert Vektoren in eingebettetem Qdrant,
        │  leitet Nutzerfragen an konfigurierten OpenAI-kompatiblen LLM
        ▼
Web-UI über Home-Assistant-Ingress
```

## Installation (HACS, empfohlen)

1. **Einstellungen → Add-ons → Add-on Store → ⋮ (oben rechts) → Repositories**
2. `https://github.com/dibi73/ha-bookstack-rag-addon` einfügen, **Hinzufügen**.
3. Das "BookStack RAG"-Add-on erscheint im Store. **Installieren** klicken.
4. Export-Pfad konfigurieren (Default: `/config/bookstack_export` — passt zur
   Default-Konfiguration der Integration).
5. **Starten**. Der Ingress-Panel-Link erscheint in der HA-Sidebar.

## Konfiguration

### Indexierung

| Option | Default | Beschreibung |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Pfad im Container, wo der Markdown-Export liegt. |
| `embedding_model` | `nomic-ai/nomic-embed-text-v1.5` | sentence-transformers-Modell. Default ist im Image vorinstalliert. |
| `top_k` | `5` | Default-Anzahl der Retrieval-Treffer. |

### LLM (per Default aus)

| Option | Beschreibung |
|---|---|
| `llm_base_url` | OpenAI-kompatibler Chat-Completions-Endpoint. Leer → LLM aus. |
| `llm_api_key` | Bearer-Token. Als Password-Feld markiert. Lokales Ollama lässt das leer. |
| `llm_model` | Modell-Identifier. Leer → LLM aus. |
| `llm_timeout` | Timeout pro Request in Sekunden. Default 60. |
| `max_turns` | Conversation-History-Truncation — letzte N User/Assistant-Paare. Default 20. |
| `system_prompt` | Optionaler Override des eingebauten zweisprachigen System-Prompts. |

#### Beispiel-Konfigurationen

```yaml
# Ollama im LAN (Empfehlung — lokal, privat, kostenlos)
llm_base_url: http://192.168.1.100:11434/v1
llm_api_key: ""
llm_model: qwen2.5:7b

# OpenAI
llm_base_url: https://api.openai.com/v1
llm_api_key: sk-...
llm_model: gpt-4o-mini

# Anthropic (OpenAI-Compat-Layer)
llm_base_url: https://api.anthropic.com/v1
llm_api_key: sk-ant-...
llm_model: claude-haiku-4-5

# Google Gemini (OpenAI-Compat-Endpoint)
llm_base_url: https://generativelanguage.googleapis.com/v1beta/openai
llm_api_key: AIza...
llm_model: gemini-2.0-flash
```

## Endpoints

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/status` | `{status, export_path, markdown_files, indexed, llm_configured}` |
| `POST` | `/api/query` | Body: `{text, top_k?, conversation_id?, stream?}`. Antwort: JSON `{query, top_k, hits, conversation_id?, answer?}` oder SSE-Stream mit `hit` / `delta` / `done`-Events. |
| `POST` | `/api/reindex` | Voller Reconcile-Sweep. |
| `GET` | `/api/conversations` | Liste der jüngsten Chats mit Titel-Vorschau + Message-Count. |
| `GET` | `/api/conversations/{id}` | Vollständige Message-History eines Chats. |
| `DELETE` | `/api/conversations/{id}` | Hard-Delete eines Chats. |

Alle Endpoints sind über das HA-Ingress-Panel erreichbar.

## Roadmap

- [x] **Stage 0 (v0.1.0)** — Skelett-Add-on, CI, Status-Endpoint.
- [x] **Stage 1 (v0.2.0)** — File-Watcher, Embedding (nomic-embed-text),
  Qdrant-Index, `/api/query` mit Top-K-Dokumenten.
- [x] **Stage 2 (v0.3.0)** — LLM-Integration mit Multi-Turn-Chat und
  Server-Sent-Events-Streaming über jeden OpenAI-kompatiblen Endpoint.
- [ ] **Stage 3 (v0.4.0)** — Web-UI: Eingabefeld, Antwort-Anzeige,
  Quellen-Links zurück nach BookStack.
- [ ] **Stage 4+** — HA-Conversation-Plattform-Integration
  (Sprachsteuerung), Multi-LLM-Routing, Quellen-Re-Ranking.

## Nicht-Ziele

- **Kein Write-Back nach HA oder BookStack.** Das Add-on ist Read-only-
  Konsument des Markdown-Exports. Doku lebt in BookStack (managed durch
  die Schwester-Integration); das Add-on ändert sie nie.
- **Kein eigener LLM-Server.** Du bringst deinen LLM-Endpoint mit (lokales
  Ollama, Cloud-API, …). Das Add-on konfiguriert, es hostet nicht.
- **Kein Multi-Tenant- / Multi-User-System.** Ein Haushalt, eine Installation.

## Hardware & Anforderungen

| Setup | Einschätzung |
|---|---|
| Raspberry Pi 4 (4 GB, **64-Bit-OS**) | ✅ Embedding läuft (langsam); LLM extern |
| Synology / x86-NAS | ✅ Embedding okay; kleines lokales LLM möglich |
| Lokaler PC mit GPU | ✅ Ollama dort hosten, Add-on dahin verweisen |
| Pi 4 (32-Bit-OS) oder Pi 3 | ❌ ab v0.2.0: armv7 nicht mehr unterstützt (keine PyTorch-Wheels) |
| Pi 4 (2 GB) | ⚠️ grenzwertig — Embedding-Modell allein braucht ~500 MB |

Mindest-RAM für das Add-on (ohne LLM): ~1 GB. Unterstützte Architekturen: **amd64**, **aarch64** (Pi 4/5 also auf 64-Bit-OS).

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md). Lint und Tests müssen grün
sein; neues Verhalten braucht Tests.

## Schwester-Projekt

[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) — die
HACS-Integration, die den Markdown-Export erzeugt, den dieses Add-on
liest. Beide Projekte entwickeln sich unabhängig; das Gesamtsystem
braucht beide.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
