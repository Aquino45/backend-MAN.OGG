# ESTADO — backend-MAN.OGG

Actualizado: 09/10/2026 (ticket BE-004).

## Dónde estamos
- El repo levanta con `docker compose up -d --build`: BD PostgreSQL 16 + PostGIS 3.4 (`db`) y API Django 5.2 + DRF + GeoDjango (`api`).
- Rutas (solo GET, forma exacta del contrato): `/api/v1/salud`, `/api/v1/sectores`, `/api/v1/sectores/{sector_id}/arboles` y `/api/v1/arboles/{codigo}`. 404 y todo error con `{"detail"}` en español. El admin vive en `ADMIN_RUTA` (del `.env`).
- Seguridad mínima activa: solo lectura por defecto, throttling para anónimos (`API_LIMITE_ANONIMO`), CORS con lista blanca y `SECURE_*` / cookies seguras desde el `.env`.
- Modelos `Sector` y `Arbol` (app `censo`) en el esquema `DB_ESQUEMA`, que lo crea una migración. Importadores repetibles: `importar_sectores` (5 sectores, 50.16 ha) e `importar_planilla` (118 árboles reales del S01, 34 con coordenadas).
- CI en GitHub Actions con los jobs `lint` (Ruff), `tests` (pytest contra la PostGIS del compose) y `contrato`.
- El contrato v0 vive en `contrato/` (`openapi.yaml` y `ejemplos/`) y se valida con `scripts/validar_contrato.py`.
- La arquitectura del back está escrita en `docs/ARQUITECTURA.md` (capas, árbol y quién llama a quién). Los agentes la leen antes de empezar y la QA bloquea un archivo fuera de su capa.
- Hito M0 (disciplina) en curso.

## Último ticket
- BE-004 — las 3 rutas del contrato con tests, seguridad mínima y ajustes de la § 8 de la arquitectura (EN REVISIÓN, Issue #9). Resumen en `docs/tickets/BE-004.md`.
- Antes: DOC-002 — arquitectura escrita en el back (mergeado, #8).

## Siguiente ticket
- BE-005 (árboles demo) o BE-006 (fotos), según despache el asesor.

## Pendiente fuera de este repo
- Protección de `main` (PR obligatorio con aprobación de Code Owner, status checks y solo squash).
- Checks obligatorios de `main`: `lint`, `tests` y `contrato`.
- Decisión pendiente con la brigada: los 36 árboles «muerto» del S01 (sin DAP, especie ni coordenadas) se sirven tal cual; si se sacan, va en otro ticket.
- Riesgo de BE-003: los códigos de árbol salen de un COUNTIF que depende del orden de las filas. Congelarlos en la planilla (pegar como valores) antes de seguir llenando.
- Requerimientos del stakeholder aprobados.
- DOC-002 en el front: después de que FE-001 (PR #2 del front) esté mergeado.

## Al arrancar una sesión
`docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.
