@AGENTS.md

# Exclusivo de Claude Code

## Agentes (`.claude/agents/`)
- `api-mvc`, `geo-datos`, `contrato`, `qa-revisor`.
- Cada agente lee primero `AGENTS.md` y su ticket, y termina su informe con la línea del canario del ticket.
- `qa-revisor` solo lee: no edita.

## Comandos útiles
- `claude --worktree <ID>`: trabajar un ticket en su propio worktree.
- `/clear`: entre tareas distintas y tras 2 correcciones fallidas.
- Plan mode (`Shift+Tab`): para todo lo que no quepa en una frase.

## Modelo
- Sin modelo fijado a nivel de repo; los agentes declaran el suyo en su frontmatter.

## Permisos
- `.claude/settings.json` (en git) bloquea merge, force-push y `.env`, y pide confirmación para `git push`.
- Lo personal va en `.claude/settings.local.json` (ignorado por git).
