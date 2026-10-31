# Telegram Robot Leads — Documentação

This directory is the persistent knowledge base for the project.

## Source-of-truth model

- `BOOTSTRAP.md` — **single functional source of truth** for the two accounts, regional group discovery, entry/deduplication and continuity rules.
- `PROJECT-STATE.md` — dated, evidence-backed GitHub/CI/VPS deployment status and resume point.
- `GOVERNANCE.md` — rules for creating, promoting, updating and preserving project knowledge.
- `research/` — investigations and comparisons before decisions.
- `evidence/` — sources, experiments and PoC results supporting conclusions.
- `decisions/` — Architecture Decision Records (ADRs), including superseded decisions.
- `requirements/` — accepted functional, quality, security and operational requirements.
- `architecture/` — current architecture views after they are validated.
- `risks/` — current risk register and mitigations.
- `roadmap/` — phases, gates and exit criteria.
- `checkpoints/` — durable handoff/resume snapshots for long human/AI sessions.
- `templates/` — standard record formats.

## Authority rule

Chat conversations, Issues and PR discussions are working/coordination surfaces. Durable project knowledge must be promoted into repository documentation when it becomes materially relevant.

Historical records are preserved. Living documents represent what is true now.

## Leitura recomendada

Começar por `BOOTSTRAP.md` para as regras atuais e por `PROJECT-STATE.md`
para saber o que realmente está integrado, testado e instalado. `AGENTS.md`
é a entrada de agentes; `GOVERNANCE.md` estabelece a gestão de conhecimento.

**Não transformar um protocolo antigo numa regra operacional nova.** O limite
histórico de um grupo/dia foi substituído: a pesquisa pode ter cadência diária,
mas não há quota fixa de adesões a grupos por dia. Os dois administradores
podem estar no mesmo grupo; a deduplicação é por conta e grupo.
Não existe outro framework a instalar ou sincronizar.