---
kind: remote
name: adk-reviewer
agent_card_url: https://code-review-assistant-926389250088.us-central1.run.app/.well-known/agent.json
auth:
  type: google-credentials
---
# Auditor de SQL Medallion (ADK)
Este agente especializado analiza código SQL para BigQuery siguiendo estándares de arquitectura Medallion. 
Utiliza una pipeline de ADK en Cloud Run para detectar errores y sugerir correcciones accionables.
