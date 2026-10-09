# ESTADO — backend-MAN.OGG

Actualizado: 08/10/2026 (ticket BE-002).

## Dónde estamos
- El repo levanta con `docker compose up -d --build`: BD PostgreSQL 16 + PostGIS 3.4 (`db`) y API Django 5.2 + DRF + GeoDjango (`api`).
- Única ruta: `GET /api/v1/salud` (200 con la BD arriba, 503 sin ella). Sin modelos del dominio todavía.
- CI en GitHub Actions con los jobs `lint` (Ruff), `tests` (pytest contra la PostGIS del compose) y `contrato`.
- El contrato v0 vive en `contrato/` (`openapi.yaml` y `ejemplos/`) y se valida en el CI con el job `contrato` (`scripts/validar_contrato.py`).
- Hito M0 (disciplina) en curso.

## Último ticket
- BE-002 — contrato v0 (`contrato/openapi.yaml`) con su validación en el CI (EN REVISIÓN). Resumen en `docs/tickets/BE-002.md`.

## Siguiente ticket
- BE-003 — modelos Sector y Árbol + importadores (sectores GeoJSON y planilla de la brigada).

## Pendiente fuera de este repo
- Protección de `main` (PR obligatorio con aprobación de Code Owner, status checks y solo squash).
- Al mergear BE-001: agregar `lint` y `tests` como checks obligatorios de `main`.
- Al mergear BE-002: agregar `contrato` como check obligatorio de `main`.
- Requerimientos del stakeholder aprobados.

## Al arrancar una sesión
`docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.
