# 🤖 Project Agents & Architecture

## 📋 Index
  - [Development Workflow](#development-workflow)
- [Team Context](#-team-context)
- [Nanobot System](#-nanobot-vps-primary)
  - [Architecture](#architecture)
  - [Infrastructure](#infrastructure)
- [Other Agents](#-other-agents)

---

## Development Workflow
Updates are automated via GitHub Actions.
1. **Develop**: Create a new branch for every task. Push to origin (fork). Dont forget about tests.
2. **Pull Request**: Create PR to `main` branch of origin (User's Fork).
3. **Merge**: Merge PR to trigger deployment.
4. **CI/CD Pipeline**:
   - **Build**: GitHub Actions builds the Docker image and pushes to GHCR.
   - **Deploy**: GitHub Actions connects to VPS via SSH and updates the container.
5. **Verify**: Check logs via `docker logs -f nanobot_agent`.

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


### 📡 Server Access & Logs
**DO NOT FORGET THIS.**
- **Connect**: `ssh -i .ssh/id_rsa_new_hope -o StrictHostKeyChecking=no sdgh5-234-dss@85.208.86.93`
- **View Logs**: `docker logs -f --tail 100 nanobot_agent`
- **Restart**: `cd ~/nanobot && docker compose restart nanobot_agent`

---

## ☕ Other Agents on this VPS

### Pupi Coffee Bot
- **Status**: ✅ Active
- **Type**: Telegram Bot + Web Dashboard
- **Location**: `~/pupin-cupping`
- **Port**: 8000


[def]: #deployment-workflow