# Trilogy Ai / HUF Enhanced AI Chat

HUF Enhanced AI Chat adds a Desk-native ERPNext assistant inspired by changAI-style accessibility while preserving HUF's own agent, tool, RAG, trigger, and observability architecture.

## Features
- Floating Desk chat widget.
- Full Desk page at `/app/huf-chat`.
- Unified backend API under `huf.api.chat`.
- Agent and model selection through HUF configuration.
- Permission-safe ERP schema retrieval and natural language ERP queries.
- Audit logging, redaction, feedback, and debug trace for authorized users.
- Arabic prompts and RTL-friendly UI.

## Installation
```bash
bench --site pro.trilogy-erp.com migrate
bench build --app huf
bench --site pro.trilogy-erp.com clear-cache
```

## Settings
Configure `HUF AI Settings` to enable the widget, RAG, debug roles, allowed/blocked DocTypes, redaction, and confirmation for sensitive actions. Provider keys remain in `AI Provider` password fields.

## Usage
Open ERPNext Desk and use the floating **HUF Assistant / مساعد HUF** button. The widget opens as a polished side drawer on desktop and a bottom sheet on mobile, with Arabic suggestions, Markdown tables, feedback buttons, and safe confirmation prompts for sensitive actions.

For a larger workspace, visit `/app/huf-chat`. The full page includes a session sidebar, searchable previous conversations, the same chat composer, and an optional debug panel for authorized users only.

### UX and Answer Style
- Suggested questions are clickable business chips. Clicking a chip sends the question immediately; generated follow-up suggestions can also be edited before sending when the edit option appears.
- Users can choose a focused safe agent: مساعد HUF، محلل المبيعات، محلل المخزون، مساعد المتأخرات، أو مساعد المهام. Changing the agent starts a clean context.
- Answers start with the result, mention the period/filters used, stay concise by default, and avoid unsupported suggestions such as export or email unless a safe flow exists.
- Results are permission-aware and never fabricate missing ERP numbers. Sensitive actions require explicit confirmation.
- Smart model routing is configurable in `HUF AI Settings` with `preferred_smart_model`, `preferred_fast_model`, and `use_smart_model_for_analytics`; credentials remain only in provider settings.

## Security
The API blocks Guest users, respects Frappe permissions, hides debug traces from normal users, and requires confirmation before sensitive actions.

## RAG and Tools
Schema RAG indexes accessible DocTypes and fields. HUF tools include `huf_search_erp_schema`, `huf_safe_get_list`, `huf_safe_get_doc`, and `huf_natural_language_erp_query`.


---

# HUF

**The AI-native engine for building intelligent, action-oriented systems.**

HUF sits at the intersection of knowledge, automation, and tools—enabling AI to understand business context and execute real work safely, auditably, and at scale.

[**Documentation**](https://docs.huf.ai/) | [**Report Issue**](https://github.com/tridz-dev/huf/issues) | [**Discussions**](https://github.com/tridz-dev/huf/discussions)

> ⚠️ **Security notice (LiteLLM):** LiteLLM (a HUF dependency) reported compromised PyPI releases `1.82.7` and `1.82.8` on **March 24, 2026**. HUF blocks these versions and shows an install-time alert if detected. Incident: https://github.com/BerriAI/litellm/issues/24518

<br/>

<img width="1905" height="928" alt="HUF Dashboard" src="https://github.com/user-attachments/assets/61a8511b-80cc-4843-a90c-bfcfc4a45c97" />

<br/>

> **Note:** HUF is actively being migrated from an existing implementation. Not recommended for production use at this stage.

---

## Why HUF Exists

AI adoption inside organizations is fragmented:

- **Knowledge lives in too many places** — scattered across docs, databases, and people's heads
- **Automation is rigid and rule-based** — breaks on edge cases, requires constant maintenance
- **AI tools operate in isolation** — each team rebuilds similar assistants
- **Costs, behavior, and risk are hard to control** — no visibility, no governance

HUF exists to **centralize intelligence and execution** into a single engine—so AI can be trusted to operate inside real business systems.

---

## What HUF Does

HUF is designed to be the **core AI layer** inside an organization or product, not a surface-level chatbot or a single-purpose assistant.

**One engine. Multiple ways to use it.**

| Capability | What it enables |
|------------|-----------------|
| **Multi-Provider AI** | Connect to OpenAI, Anthropic, Google, Mistral, and 100+ providers through a unified interface |
| **Intelligent Tools** | Give AI the ability to read, write, and act on your business data |
| **Knowledge Grounding** | RAG-powered context from your docs, files, and URLs |
| **Event-Driven Execution** | Trigger agents on document events, schedules, or webhooks |
| **Visual Workflow Builder** | Design complex automations with drag-and-drop flows (WIP)|
| **Full Auditability** | Every run, every tool call, every token—logged and traceable |
| **Cost Control** | Track usage and spending across models and teams |

---

## Use HUF As

### AI Infrastructure for Products

Use HUF as the **backend AI engine** for products that need intelligence, automation, and integration.

**Ideal for:**
- AI-first startups building on Frappe/ERPNext
- SaaS products adding AI capabilities
- Platforms that need agent orchestration, cost control, and auditability

HUF handles reasoning, knowledge, tool execution, and governance—so product teams can focus on user experience.

---

### Internal Intelligence Platform

Use HUF to power **internal AI experiences** grounded in company knowledge.

**Build:**
- Internal chat systems that know your business
- Role-based assistants for Ops, HR, Sales, Support
- Knowledge discovery and employee onboarding tools

Replace disconnected internal AI tools with a single, governed intelligence layer.

---

### Automation & Orchestration Engine

Use HUF to build **AI-driven workflows** that reason and act across systems.

**Suited for:**
- Multi-step processes that span departments
- Cross-tool automation with conditional logic
- Intelligent approvals, routing, and escalations

Unlike traditional automation, HUF adapts to context instead of breaking on edge cases.

---

### Embedded AI Layer for SaaS

Use HUF to **embed AI directly into products** without building custom infrastructure.

**Enable:**
- In-app copilots and assistants
- Customer-facing AI features
- Vertical AI capabilities with clear permission boundaries

HUF provides a shared AI backend with cost, behavior, and access controls built in.

---

### Enterprise AI Control Plane

Use HUF as a **governed control layer** for AI across the organization.

**Critical for:**
- Cost management and budget allocation
- Auditability and compliance requirements
- Tool and model governance
- Responsible AI deployment at scale

Give leadership visibility and control without slowing down teams.

---

## Core Capabilities

### Agent System

Create AI agents with custom instructions, connect them to any LLM provider, and equip them with tools to take action:

- **CRUD Operations** — Read, create, update, delete documents
- **Custom Functions** — Connect any Python function as a tool
- **HTTP Requests** — Call external APIs and services
- **Agent Chaining** — Agents can trigger other agents
- **MCP Integration** — Connect to external tool providers (Gmail, GitHub, Slack, etc.)

### Knowledge Management

Ground AI responses in your actual business knowledge:

- **Multiple Input Types** — Files, text, URLs
- **Automatic Chunking** — Intelligent text segmentation
- **Fast Search** — BM25-powered retrieval via SQLite FTS5
- **Flexible Injection** — Mandatory context or on-demand search

### Trigger System

Run agents automatically based on events:

- **Document Events** — `after_insert`, `on_submit`, `on_cancel`, and more
- **Schedules** — Hourly, daily, weekly, monthly, yearly intervals
- **Webhooks** — HTTP endpoints with authentication
- **Conditional Logic** — Python expressions to control execution

### Visual Flow Builder

Design complex workflows with a modern React-based interface:

- **Drag-and-Drop Canvas** — Build flows visually
- **Node Types** — Triggers, actions, utilities, conditions
- **Real-Time Editing** — See changes instantly
- **App Integrations** — Gmail, Calendar, Slack, Notion, HubSpot

### Observability

Full visibility into what your AI is doing:

- **Agent Runs** — Status, prompt, response, token usage, cost
- **Conversations** — Complete chat history with context
- **Tool Calls** — Every tool invocation with arguments and results
- **Feedback System** — Capture user ratings for quality improvement

---

## Quick Start

### Try with Docker

```bash
git clone https://github.com/tridz-dev/huf.git
cd huf/docker
docker compose up
```

Open http://localhost:8000 and login:
- **User:** Administrator
- **Password:** admin

### Install on Existing Bench

```bash
bench get-app git@github.com:tridz-dev/huf.git
bench install-app huf
bench setup requirements
bench restart
```

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                         HUF Engine                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐         │
│  │   Agents     │  │  Knowledge   │  │   Triggers     │         │
│  │              │  │              │  │                │         │
│  │ Instructions │  │ RAG/FTS5     │  │ Events         │         │
│  │ Tools        │  │ Chunking     │  │ Schedules      │         │
│  │ Parameters   │  │ Retrieval    │  │ Webhooks (WIP) │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬─────────┘         │
│         │                 │                 │                   │
│         └────────────────┬┴─────────────────┘                   │
│                          │                                      │
│  ┌───────────────────────▼───────────────────────────────────┐  │
│  │                   Execution Layer                         │  │
│  │                                                           │  │
│  │  LiteLLM (100+ providers) │ Tool System │ MCP Client      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Observability                            │ │
│  │                                                            │ │
│  │  Runs │ Conversations │ Messages │ Tool Calls │ Costs      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌───────────────┐
   │  Chat   │          │  API    │          │     Flows     │
   │   UI    │          │ Endpoint│          │ Builder (WIP) │
   └─────────┘          └─────────┘          └───────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Frappe Framework, Python 3.10+ |
| **AI Integration** | LiteLLM |
| **Knowledge** | SQLite FTS5 (LlamaIndex) & multiple VectorDBs WIP.  | 
| **Frontend** | React 18, TypeScript, Tailwind CSS |
| **Flow Builder** | React Flow / XYFlow | (WIP)
| **Database** | MariaDB |

---

## Security Notice (LiteLLM)

LiteLLM is a core dependency of Huf. On **March 24, 2026**, the LiteLLM team reported a supply-chain compromise affecting published releases (`1.82.7` and `1.82.8`) that included a malicious `.pth` startup payload.

What Huf has done:
- Blocked compromised versions in dependency constraints (`litellm>=1.0.0,!=1.82.7,!=1.82.8`).
- Added install-time detection in `huf/install.py` to show a critical alert if a compromised LiteLLM version is already present in the environment.

Upstream incident thread:
- https://github.com/BerriAI/litellm/issues/24518

---

## Documentation

- [**Full Documentation**](https://docs.huf.ai/) — Guides, tutorials, and API reference
- [**AGENTS.md**](./AGENTS.md) — Technical context for AI agents. Adopts the [agents.md](https://agents.md) standard.
- [**CLAUDE.md**](./CLAUDE.md) — Defines coding standards, review criteria, and project-specific rules. Claude reads this file during runs and follows your conventions.


---

## License

MIT License — see [LICENSE](./LICENSE) for details.

---

<p align="center">
  <strong>Built for teams who want AI that actually works.</strong>
</p>
