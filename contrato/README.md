# Contrato (back ↔ front)

`openapi.yaml` es el contrato de la API del Censo arbóreo UPeU Lima (OpenAPI 3.1). **Manda sobre el back y sobre el front**: si el código y el contrato se contradicen, el que está mal es el código.

## Regla de cambios
Un campo nuevo, o uno que cambia, exige **primero un ticket de contrato** (que solo toca esta carpeta), **después el ticket del back** y **al final el del front**. Los nombres llevan la unidad incluida (`_m`, `_cm`, `_kg`) y los datos de prueba llevan `demo: true`.

## Cómo genera el front sus tipos
Desde la raíz del repo del front, con la ruta local de este contrato en `CONTRATO_RUTA` (en el `.env` del front):

```bash
npm run contrato:tipos
```

El script (`scripts/generar-tipos.mjs` del front) genera `src/api/schema.d.ts` con `openapi-typescript`.

## Cómo se valida
Desde la raíz de este repo (Git Bash):

```bash
docker compose run --rm --no-deps api python scripts/validar_contrato.py
```

Comprueba que el YAML es OpenAPI 3.1 válido y que cada ejemplo cumple su schema (JSON Schema Draft 2020-12). El mismo chequeo corre en `tests/core/test_contrato.py` y en el job `contrato` del CI.

## Ejemplos y su schema
| Ejemplo | Schema |
|---|---|
| `ejemplos/sectores.json` | `SectorColeccion` |
| `ejemplos/sector-1-arboles.json` | `ArbolResumenColeccion` |
| `ejemplos/arbol-real.json` | `Arbol` |
| `ejemplos/arbol-demo.json` | `Arbol` |

La lista vive, de forma declarativa, en `scripts/validar_contrato.py` (`EJEMPLOS`).

## Atribución
Contorno del campus © colaboradores de OpenStreetMap, ODbL (`ejemplos/sectores.json`).
