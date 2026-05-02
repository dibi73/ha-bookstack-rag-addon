# BookStack RAG — Home-Assistant-Add-on

> Verfügbar auf: [English](README.md) · **Deutsch**

Ein Home-Assistant-Add-on, das den Markdown-Export der Schwester-Integration
[`ha-bookstack-sync`](https://github.com/dibi73/ha-bookstack-sync) lokal
indexiert und die Smart-Home-Doku per natürlicher Sprache abfragbar macht —
über einen frei konfigurierbaren OpenAI-kompatiblen LLM-Endpoint (Ollama,
OpenAI, Anthropic via Proxy, …) und eine einfache Web-UI für die ganze
Familie.

## Status

**Stage 0 — v0.1.0** (Skelett-Release).

Dieses Release enthält:
- Die HACS-Add-on-Repository-Struktur.
- Einen minimalen FastAPI-Server, der nach Installation meldet, wie viele
  `.md`-Dateien er unter dem konfigurierten BookStack-Export-Pfad sieht.
- Das CI-Gerüst (ruff-Lint, pytest, Container-Build) für alle folgenden
  Stages.

Indexierung, Embedding, RAG und Web-UI kommen ab v0.2.0 — siehe
[Roadmap](#roadmap).

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

## Konfiguration (Stage 0)

| Option | Default | Beschreibung |
|---|---|---|
| `bookstack_export_path` | `/config/bookstack_export` | Pfad im Container, wo der Markdown-Export liegt. Default passt, wenn `ha-bookstack-sync` mit seinem Default-Export-Pfad genutzt wird. |

Weitere Optionen (LLM-Endpoint, Modell-Name, top-k, …) folgen mit den
nächsten Stages. Dokumentation in `bookstack-rag/DOCS.md`.

## Endpoints (Stage 0)

| Methode | Pfad | Antwort |
|---|---|---|
| `GET` | `/api/status` | `{"status": "ok", "export_path": ..., "markdown_files": N}` |

Erreichbar über das HA-Ingress-Panel.

## Roadmap

- [x] **Stage 0 (v0.1.0)** — Skelett-Add-on, CI, Status-Endpoint.
- [ ] **Stage 1 (v0.2.0)** — File-Watcher, Embedding (nomic-embed-text),
  Qdrant-Index, `/api/query` mit Top-K-Dokumenten.
- [ ] **Stage 2 (v0.3.0)** — LLM-Integration (OpenAI-kompatibler Endpoint
  konfigurierbar, Streaming-Antworten).
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
