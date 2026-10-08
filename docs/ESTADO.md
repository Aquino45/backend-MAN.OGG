# ESTADO — backend-MAN.OGG

Actualizado: 08/10/2026 (ticket DOC-001).

## Dónde estamos
- El repo tiene solo la base de gobierno: reglas, plantillas, config de Claude Code y VS Code. No hay código de aplicación.
- Hito M0 (disciplina) en curso.

## Último ticket
- DOC-001 — base de gobierno de los 2 repos (EN REVISIÓN). Resumen en `docs/tickets/DOC-001.md`.

## Siguiente ticket
- BE-001 — mover el Docker de la BD al repo y CI mínimo (Django, docker-compose y `.env.example`).

## Pendiente fuera de este repo
- Protección de `main` (PR obligatorio con aprobación de Code Owner, status checks y solo squash).
- Requerimientos del stakeholder aprobados y contrato v0.

## Al arrancar una sesión
`docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.
