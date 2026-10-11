# ESTADO — backend-MAN.OGG

Actualizado: 11/10/2026 (ticket BE-008).

## Dónde estamos
- El repo levanta con `docker compose up -d --build`: BD PostgreSQL 16 + PostGIS 3.4 (`db`) y API Django 5.2 + DRF + GeoDjango (`api`).
- Rutas (solo GET, forma exacta del contrato): `/api/v1/salud`, `/api/v1/sectores`, `/api/v1/sectores/{sector_id}/arboles` y `/api/v1/arboles/{codigo}`. 404 y todo error con `{"detail"}` en español. El admin vive en `ADMIN_RUTA` (del `.env`).
- Seguridad mínima activa: solo lectura por defecto, throttling para anónimos (`API_LIMITE_ANONIMO`), CORS con lista blanca y `SECURE_*` / cookies seguras desde el `.env`.
- Modelos `Sector` y `Arbol` (app `censo`) en el esquema `DB_ESQUEMA`, que lo crea una migración. Importadores repetibles: `importar_sectores` (5 sectores, 50.16 ha) e `importar_planilla` (118 árboles reales del S01, 34 con coordenadas).
- CI en GitHub Actions con los jobs `lint` (Ruff), `tests` (pytest contra la PostGIS del compose) y `contrato`.
- El contrato vive en `contrato/` (`openapi.yaml` 0.3.0 y `ejemplos/`) y se valida con `scripts/validar_contrato.py`. La cartilla (`/arboles/{codigo}`) entrega también `origen`, `identificacion`, `observaciones` y las UTM guardadas (`utm_este_m`, `utm_norte_m`, con `DECIMALES_UTM`).
- Cartilla y resumen entregan el `uid` del árbol (UUID estable, no cambia aunque cambie el `codigo`; el `id` numérico no sale por la API) y la marca de árbol destacado (`destacado`, `motivo_destacado`), con hasta `TOPE_DESTACADOS_POR_SECTOR` por sector validado en `Arbol.clean()`. Las rutas siguen por `codigo`.
- La arquitectura del back está escrita en `docs/ARQUITECTURA.md` (capas, árbol y quién llama a quién). Los agentes la leen antes de empezar y la QA bloquea un archivo fuera de su capa.
- Hito M0 (disciplina) en curso.

## Último ticket
- BE-008 — contrato 0.3.0: `uid` del árbol y árboles destacados (EN REVISIÓN, Issue #17). Resumen en `docs/tickets/BE-008.md`.
- Antes: DOC-004 (parte del back) — nombre público y docs neutras (mergeado, #16).

## Siguiente ticket
- BE-010 (producción en Render) y, con BE-008 mergeado, BE-005 (cargar los árboles demo).

## Estado actual frente al objetivo (09/10/2026)
Viene de la § 8 que tenía `docs/ARQUITECTURA.md` hasta DOC-004; cada fila se comprobó en el árbol de `main`.

| Pieza | Hoy | Se ajustó en |
|---|---|---|
| `apps/censo/models.py`, `servicios/`, `admin.py`, `management/` | ✅ como en el árbol | BE-003 |
| Salud (`views.py` y `urls.py`) | ✅ en `apps/core/api/`, misma ruta | BE-004 |
| `test_salud.py`, `test_configuracion.py`, `test_contrato.py` | ✅ en `tests/core/` | BE-004 |
| `selectores.py`, `api/` de censo, `excepciones.py`, `seguridad.py` | ✅ existen y siguen las capas | BE-004 |
| Admin | ✅ en `ADMIN_RUTA` desde `.env` (`config/urls.py`) | BE-004 |
| 2 constantes de `importar_sectores.py` | ✅ en `config/constantes.py` | BE-004 |
| `*.xlsx` en `.gitignore` | ✅ | DOC-002 |

## Pendiente fuera de este repo
- Protección de `main` (PR obligatorio con aprobación de Code Owner, status checks y solo squash).
- Checks obligatorios de `main`: `lint`, `tests` y `contrato`.
- Decisión pendiente con la brigada: los 36 árboles «muerto» del S01 (sin DAP, especie ni coordenadas) se sirven tal cual; si se sacan, va en otro ticket.
- Riesgo de BE-003: los códigos de árbol salen de un COUNTIF que depende del orden de las filas. Congelarlos en la planilla (pegar como valores) antes de seguir llenando.
- Requerimientos del stakeholder aprobados.
- DOC-002 en el front: después de que FE-001 (PR #2 del front) esté mergeado.

## Al arrancar una sesión
`docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.
