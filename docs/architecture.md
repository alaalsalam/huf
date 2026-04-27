# HUF Enhanced AI Chat Architecture

HUF Enhanced AI Chat exposes a Desk-native assistant through `huf.api.chat`. It reuses HUF Agent, Conversation, Message, Run, Tool Call, Provider, Model, Knowledge Source, and Knowledge Input records. ERP access is performed through permission-safe Frappe APIs and schema retrieval. Sensitive actions are routed through confirmation and audit logging.
