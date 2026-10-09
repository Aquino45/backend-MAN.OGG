# ESTADO — backend-MAN.OGG

Actualizado: 09/10/2026 (ticket BE-003).

## Dónde estamos
- El repo levanta con `docker compose up -d --build`: BD PostgreSQL 16 + PostGIS 3.4 (`db`) y API Django 5.2 + DRF + GeoDjango (`api`).
- Única ruta: `GET /api/v1/salud` (200 con la BD arriba, 503 sin ella), más el admin en `/admin/`.
- Modelos `Sector` y `Arbol` (app `censo`) en el esquema `DB_ESQUEMA`, que lo crea una migración. Importadores repetibles: `importar_sectores` (5 sectores, 50.16 ha) e `importar_planilla` (118 árboles reales del S01, 34 con coordenadas).
- CI en GitHub Actions con los jobs `lint` (Ruff), `tests` (pytest contra la PostGIS del compose) y `contrato`.
- El contrato v0 vive en `contrato/` (`openapi.yaml` y `ejemplos/`) y se valida con `scripts/validar_contrato.py`.
- Hito M0 (disciplina) en curso.

## Último ticket
- BE-003 — modelos Sector y Árbol + importadores (EN REVISIÓN). Resumen en `docs/tickets/BE-003.md`.

## Siguiente ticket
- BE-004 — las 3 rutas del contrato (`/sectores`, `/sectores/{id}/arboles`, `/arboles/{codigo}`), con tests.

## Pendiente fuera de este repo
- Protección de `main` (PR obligatorio con aprobación de Code Owner, status checks y solo squash).
- Checks obligatorios de `main`: `lint`, `tests` y `contrato`.
- Riesgo de BE-003: los códigos de árbol salen de un COUNTIF que depende del orden de las filas. Congelarlos en la planilla (pegar como valores) antes de seguir llenando.
- Requerimientos del stakeholder aprobados.

## Al arrancar una sesión
`docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.
