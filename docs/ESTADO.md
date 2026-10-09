# ESTADO — backend-MAN.OGG

Actualizado: 08/10/2026 (ticket BE-001).

## Dónde estamos
- El repo levanta con `docker compose up -d --build`: BD PostgreSQL 16 + PostGIS 3.4 (`db`) y API Django 5.2 + DRF + GeoDjango (`api`).
- Única ruta: `GET /api/v1/salud` (200 con la BD arriba, 503 sin ella). Sin modelos del dominio ni contrato todavía.
- CI en GitHub Actions con los jobs `lint` (Ruff) y `tests` (pytest contra la PostGIS del compose).
- Hito M0 (disciplina) en curso.

## Último ticket
- BE-001 — base del back: Django + GeoDjango + Docker + CI (EN REVISIÓN). Resumen en `docs/tickets/BE-001.md`.

## Siguiente ticket
- BE-002 — contrato v0 (`contrato/openapi.yaml`), con la ruta de salud.

## Pendiente fuera de este repo
- Protección de `main` (PR obligatorio con aprobación de Code Owner, status checks y solo squash).
- Al mergear BE-001: agregar `lint` y `tests` como checks obligatorios de `main`.
- Requerimientos del stakeholder aprobados y contrato v0.

## Al arrancar una sesión
`docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.
