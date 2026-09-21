# Changelog

## Decision briefs · 2026-09-21

- Optional shared decision question, with one latest position per selected agent:
  proceed, revise, or insufficient evidence; rationale, next check and source IDs.
- Collected-source validation, explicit missing/failed responses, separate
  agreement and completeness. No confidence scores, voting or automatic approval.
- Previous structured positions accompany the bounded conversation context.
- Local plain-text snapshot with preview, mission provenance and sharing warning.
  It excludes the raw brief, chat and transcript; model-written text may still
  contain sensitive project content and must be reviewed.
- Three no-key public examples now end with explicitly fictional decision briefs.
- Additive SQLite migration preserves existing missions. No Jev dependency,
  new provider call, paid fallback or automatic publication was introduced.

## International welcome and workspace · 2026-09-21

- English-first interface with a persistent French language choice, including
  projects, mission controls, agent exchanges and known error messages.
- Public product walkthrough with three clearly fictional, interactive examples:
  repository, website and idea. No operator key, model call or private data needed.
- Setup and private workspace entry are separate from product discovery.
- Runner instructions ask agents to follow the mission brief’s language.
- User-written context and past contributions remain in their original language.
- Signing out clears private rendered content and ignores delayed responses from
  the previous session. Failed login keeps the retry form accessible.

## Version publique initiale — 21 septembre 2026

- Vue « Autour de la table » : questions/réponses dirigées, agent actif et
  prochain intervenant, animation suspendable et prise en charge du mouvement réduit.
- Distribution MIT et guide d’installation avec les accès propres à chacun.
- Projets avec description seule, dépôt seul, URL seule ou sources combinées.
- Discussion persistante par projet, transmise aux agents lors des missions.
- Profils locaux, API et CLI configurables dans un fichier privé.
- Nouvelle installation vide ; continuité explicite pour l’installation historique.
