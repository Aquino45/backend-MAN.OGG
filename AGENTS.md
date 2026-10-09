# AGENTS.md — backend-MAN.OGG

Reglas del repo para cualquier integrante y para su Claude Code. Si algo choca con el master plan, manda este archivo.

## 1. Qué es MAN.OGG y qué es este repo
MAN.OGG es un sistema web de **censo arbóreo** con un mapa del campus UPeU Ñaña dividido en 5 sectores, para ver las características de cada árbol. Son dos repos de GitHub: `Aquino45/backend-MAN.OGG` y `Aquino45/frontend-MAN.OGG`.

Este repo es el **back**: API REST (arquitectura MVC/MVT) con Python 3.12, Django 5, Django REST Framework y GeoDjango sobre PostgreSQL 16 + PostGIS 3.4, todo en Docker. Aquí vive el contrato `contrato/openapi.yaml`.

Stack completo: back Django 5 + DRF + GeoDjango + PostgreSQL/PostGIS en Docker; front React + Vite + TypeScript + Framer Motion (+ MapLibre GL opcional).

## 2. Reglas de oro
- **Todo nace de un ticket** (Issue en GitHub + `docs/tickets/<ID>.md`).
- **Solo se tocan los «Archivos permitidos»** del ticket. La config de agentes (`.claude/`) también cambia solo por ticket.
- El contrato `contrato/openapi.yaml` (en este repo) manda. Un campo nuevo exige primero un ticket de contrato, después el back y al final el front.
- **Nunca se inventan datos del censo.** Todo árbol lleva `fuente`; los datos de prueba van solo en fixtures, con `demo: true`.
- **Tests obligatorios** en cada pieza nueva. Nunca push con tests en rojo.
- **Nunca** push a `main`, merge, force-push ni `.env` en git. Los repos son públicos: tampoco claves ni datos personales.

## 3. Cero hardcoding
- Configuración y secretos: `.env` + `.env.example`.
- Constantes de negocio en `config/constantes.py`. Configuración y secretos en `.env` (documentado en `.env.example`), leídos en `settings.py`.
- Colores, tipografía y espacios: tokens en `src/styles/tokens.css` (front). Ningún hex suelto en los componentes.
- Datos (sectores, árboles, catálogos): salen de la BD por la API, nunca de listas escritas en el código.
- URLs y puertos salen del entorno, nunca `localhost` escrito a mano.
- Nombres iguales al contrato (`codigo`, `dap_cm`, `co2_almacenado_kg`…), con la unidad incluida (`_m`, `_cm`, `_kg`). Variables descriptivas: nada de `x`, `data2` ni `tmp`. Python en `snake_case`; constantes en `MAYUSCULAS`.
- Archivos de ~300 líneas como máximo. Agregar un sector, un árbol o un campo no debe exigir tocar la lógica.

## 4. Flujo de un ticket
1. Issue → rama `ticket/<ID>-<slug>` o `claude --worktree <ID>`.
2. Tests primero.
3. Commits `[ID] descripción`.
4. Ticket en EN REVISIÓN con un resumen de ≤10 líneas que incluye «Hice fuera de lo pedido» y la línea del canario.
5. PR con `Closes #n` → CI verde → aprobación del Code Owner → squash.

## 5. Canario
- Apertura de toda respuesta: `Zapatito roto.`
- Cierre: `Zapatito roto · <ROL> · <palabra>`.
- La palabra del ticket se asigna al despachar.
- Un informe sin canario o con la palabra equivocada se rechaza y se relanza con contexto fresco.
- Familia de palabras de este repo: back = rocas sedimentarias. Registro en `docs/CANARIOS.md`.

## 6. Sesiones
- Máximo 3 tickets por sesión de orquestador.
- `/clear` al cerrar el lote, cerca de ~150k tokens y tras 2 correcciones fallidas.
- Al arrancar, en este orden: `docs/ESTADO.md` → `git log --oneline -5` → `git status` → canario.

## 7. Evidencia o no pasó
Cada afirmación del informe lleva un test, un comando corrido o un `archivo:línea`. Si no, va marcada «(sin verificar)».

## 8. Comandos
En Git Bash, desde la raíz del repo (los puertos y claves salen de tu `.env`):
- Preparar: `cp .env.example .env`
- Levantar: `docker compose up -d --build`
- Apagar: `docker compose down` (sin `-v`, para conservar los datos)
- Tests (contra la PostGIS real): `docker compose run --rm api pytest`
- Lint: `ruff check .`
- Formato: `ruff format --check .` (para aplicarlo: `ruff format .`)
- Contrato: `docker compose run --rm --no-deps api python scripts/validar_contrato.py`
