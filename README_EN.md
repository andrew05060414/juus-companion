# Juus Companion (juus-companion)

[English Documentation](README_EN.md) ｜ [中文说明](README.md)

> Created: 2026-09-27 ｜ Last Updated: 2026-10-16 ｜ Version: v0.2 (M6 Release Ready)

An AI-powered Azur Lane fan companion that **actively messages you**: each shipgirl acts as an independent conversation member. You can chat one-on-one or engage in small group chats mirroring in-game "JUUs" dynamics; they initiate messages according to their personalities, post on their JUUs social feed, and remind you of daily tasks with guaranteed notification delivery.

> **Non-Official Fan Project Notice**: This project is an independent fan creation with no commercial or operational affiliation with Manjuu Co., Ltd., Yongshi Technology, bilibili, Yostar, or the official Azur Lane team. This repository **does NOT contain** any official game dialogue texts, voice audio files, character illustrations, Live2D assets, or pre-generated persona cards. These assets must be generated locally by the user for offline personal study and research.

---

## Key Features

- **Independent Shipgirl Personas**: Each shipgirl has her own avatar, identity, and distinctive tone with real-time streaming output.
- **Proactive Messages & Reminders**: Scheduled morning wake-ups, study accountability reminders, and quiet hours tailored to individual character lore.
- **Multi-Member Group Chat Director**: Supports 2–6 shipgirls chatting together; our Director engine coordinates conversational turns and uses `[SKIP]` tags to prevent circular echo chambers.
- **JUUs Social Feed**: Characters post status updates, leave comments on each other's posts, and tag the Commander spontaneously.
- **Guaranteed Dual Push Routing**: FCM (primary channel) paired with self-hosted `ntfy` (fallback). A server-side delivery ledger syncs unread messages upon app launch with zero duplicates.
- **Long-term Memory & Context**: Short-term conversation history backed by persistent memory modules (Chronicle / Mnemosyne) to recall previous interactions and commander context.
- **Foldable & Tablet Optimization**: Dual-pane layout (session list + chat view) for unfolded devices (such as Samsung Galaxy Z Fold 7) and single-pane view for folded mode.

---

## Project Documentation

- **Architecture & Requirements**:
  - [Product Requirements Document (PRD)](docs/PRD.md)
  - [System Architecture](docs/ARCHITECTURE.md)
  - [Roadmap & Milestones](docs/ROADMAP.md)
  - [Data, Privacy & Open Source Policy](docs/DATA_POLICY.md)
  - [Decisions (ADR)](docs/decisions/) (ADR-0003 Accepted: Standalone Brain Service as long-term core)
- **Deployment & Release**:
  - [M6 Full Release Audit Report](docs/release-audit-report.md)
  - [Self-Hosting Deployment Guide](deploy/README.md)
  - [Promotional Demo Video Script](docs/demo-video-script.md)
  - [AI Agent Rules & Development Charter](AGENTS.md)

---

## Repository Modules

| Directory | Module Description | License | Status |
|---|---|:---:|:---:|
| `server/` | Juus Brain service: persona registry, sessions, director, proactive scheduler, delivery ledger | AGPL-3.0 | Core contracts & API draft complete |
| `pipeline/` | Data pipeline: extracts unpacked game configs and compiles SillyTavern / AstrBot cards locally | AGPL-3.0 | v1 pipeline implemented |
| `deploy/` | Self-hosting templates: Docker Compose, environment templates, ntfy push server | AGPL-3.0 | Production-ready |
| `adapters/` | External adapters: AstrBot integration, Chronicle personal memory connector | AGPL-3.0 | Planned |
| `app-android/` | Android client (forked from [oneroomlife/blyy](https://github.com/oneroomlife/blyy)) | GPL-3.0 | Source audited, awaiting integration |
| `pwa/` | Web / iOS PWA client | AGPL-3.0 | Planned |

---

## Development & Local Verification

### Prerequisites

The toolchain requires Python 3.12 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync
```

### Environment Setup

```sh
cp .env.example .env
```

Configure your local model gateway endpoint and API key in `.env`.

### Verification & Quality Gates

Run the local checks required by CI before submitting:

```sh
# 1. Code linting and formatting
uv run ruff check .
uv run ruff format --check .

# 2. Automated test suite
uv run pytest

# 3. Media & Asset Guard (blocks audio, images, Live2D, and large binaries)
uv run python tools/check_repository_guard.py

# 4. Full Release Auditor (scans git history, secrets, and private network leaks)
uv run python tools/audit_release.py
```

---

## Persona Data Pipeline

The pipeline generates SillyTavern persona cards and lorebooks on your local machine. All extracted texts and generated persona cards remain inside the gitignored `data/` folder, ensuring zero copyright infringement in source control:

```sh
uv run python pipeline/run.py

uv run pytest tests/test_batch.py tests/test_e2e_pipeline.py tests/test_exporter.py tests/test_extractor.py tests/test_fetcher.py tests/test_generator.py tests/test_validator.py
```

---

## Self-Hosting Deployment

Refer to the complete deployment guide in [deploy/README.md](deploy/README.md):

```sh
cd deploy
cp .env.example .env
docker compose -f docker-compose.example.yml up -d
```

---

## License & Legal Notice

1. **Licenses**:
   - The Android client in `app-android/` is licensed under **GPL-3.0** (inherited from upstream project `blyy`).
   - The rest of the project is licensed under **AGPL-3.0** (see [LICENSE](LICENSE)).
2. **Legal Disclaimer**:
   - Azur Lane and its associated characters, audio, artwork, worldbuilding, and official texts are the intellectual property of their respective copyright owners (Shanghai Manjuu Network, Shanghai Yongshi Network, bilibili, Yostar, etc.).
   - This project is developed strictly for non-commercial fan appreciation and technical research. No official proprietary assets are distributed through this repository.
