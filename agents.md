# 🤖 Project Agents & Architecture

## 📋 Index
- [Team Context](#-team-context)
- [Nanobot System](#-nanobot-vps-primary)
  - [Architecture](#architecture)
  - [Infrastructure](#infrastructure)
  - [Deployment Workflow](#deployment-workflow)
- [Other Agents](#-other-agents)

---

## 🛠 Team Context
**Role**: Personal Bot Deployment & Development Team.
**Mission**: Maintain and evolve a personal AI assistant (Nanobot) running on self-hosted infrastructure. We handle code implementation, server configuration, and reliability engineering.

---

## 🚀 Nanobot (VPS) [Primary]
**Status**: ✅ Deployed & Active
**Type**: Personal AI Assistant / Full-Stack Engineer

### Architecture
A modular Python-based agent framework designed for autonomy and extensibility.
- **Core**: Python 3.11+ custom framework (`nanobot` package).
- **Brain (LLM)**: `google/gemini-3-pro-preview` via OpenRouter.
- **Hearing (STT)**:
  - **Primary (RU)**: **Cloud.ru** (Whisper Large V3).
  - **Fallback**: **Groq** (Whisper).
- **Interface**: Telegram Bot (Long Polling).
- **Capabilities**:
  - Docker Management (via mounted socket).
  - System Code Execution (Sandbox).
  - File System Operations.

### Infrastructure
- **Host**: VPS (IP: `85.208.86.93`, OS: Debian/Linux).
- **Runtime**: Docker Compose (`nanobot_agent` container).
- **Directory Structure**:
  - `~/nanobot`: Project root.
  - `~/nanobot/nanobot_workspace`: Persisted agent workspace (memory, docs).
  - `~/nanobot/config.json`: Configuration & API Keys (Secrets).

### Deployment Workflow
Updates are applied directly to the VPS and require a container rebuild to take effect.
1. **Sync**: Transfer code/config changes to `~/nanobot`.
2. **Update**: Execute `./update.sh`.
   - `docker compose build --no-cache`: Rebuilds image with new code.
   - `docker compose up -d`: Recreates container.
3. **Verify**: Check logs via `docker logs -f nanobot_agent`.

### 📡 Server Access & Logs
**DO NOT FORGET THIS.**
- **Connect**: `ssh -i .ssh/id_rsa_new_hope -o StrictHostKeyChecking=no sdgh5-234-dss@85.208.86.93`
- **View Logs**: `docker logs -f --tail 100 nanobot_agent`
- **Restart**: `cd ~/nanobot && docker compose restart nanobot_agent`

---

## ☕ Other Agents

### Pupi Coffee Bot
- **Status**: ✅ Active
- **Type**: Telegram Bot + Web Dashboard
- **Location**: `~/pupin-cupping`
- **Port**: 8000
