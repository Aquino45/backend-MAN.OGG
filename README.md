# backend-MAN.OGG

API de **MAN.OGG**, sistema web de censo arbóreo del campus UPeU Ñaña con un mapa dividido en sectores. Este repo es el back: Django 5 + Django REST Framework + GeoDjango sobre PostgreSQL 16 + PostGIS 3.4, en Docker. Aquí vive el contrato `contrato/openapi.yaml`, que manda sobre el front.

## Levantar
Requiere Docker. En Git Bash, desde la raíz del repo:

```bash
cp .env.example .env          # y cambia las claves (POSTGRES_PASSWORD, DJANGO_SECRET_KEY)
docker compose up -d --build  # levanta la BD PostGIS (db) y la API Django (api)
```

Después abre `http://localhost:<API_PUERTO>/api/v1/salud` (el puerto está en tu `.env`). Con todo en orden responde `200` con `{"estado": "ok", ...}`.

Apagar: `docker compose down` (los datos se conservan; `-v` los borra).

## Rutas de la API
Todas cuelgan de `/api/v1/`, son de solo lectura (GET) y responden con la forma exacta de [`contrato/openapi.yaml`](contrato/openapi.yaml):

| Ruta | Qué devuelve |
|---|---|
| `GET /api/v1/salud` | Estado de la API y de la BD (`200` o `503`). |
| `GET /api/v1/sectores` | Los sectores como GeoJSON (polígonos en WGS84) con su `total_arboles`. |
| `GET /api/v1/sectores/{sector_id}/arboles` | Los árboles del sector como GeoJSON (puntos en WGS84), ordenados por `codigo`. |
| `GET /api/v1/arboles/{codigo}` | La cartilla completa de un árbol (por ejemplo `S01-A001`). |

Un sector o un árbol que no existe, o un código mal formado, da `404` con `{"detail": "No encontrado."}`. Todo error sale con ese formato, en español y sin trazas. Un POST, PUT, PATCH o DELETE se rechaza.

El admin de Django vive en `/<ADMIN_RUTA>` (de tu `.env`), no en `/admin/`.

## Variables de seguridad
Además de la BD y Django, el `.env` lleva (todas documentadas en [`.env.example`](.env.example)):
- `ADMIN_RUTA`: ruta del admin.
- `API_LIMITE_ANONIMO`: peticiones por IP que acepta la API (por ejemplo `120/min`); al pasarlo responde `429`.
- `CORS_ORIGENES_PERMITIDOS` y `DJANGO_ALLOWED_HOSTS`: listas blancas del front y de los hosts.
- `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SESSION_COOKIE_SECURE` y `DJANGO_CSRF_COOKIE_SECURE`: apagados en desarrollo; en producción, HTTPS y cookies seguras.

## Cargar datos
Con los contenedores arriba, en Git Bash:

```bash
docker compose run --rm api python manage.py migrate
docker compose run --rm api python manage.py importar_sectores datos/sectores/sectores-utm18s-v0.geojson
MSYS_NO_PATHCONV=1 docker compose run --rm -v /ruta/local/arb2-corregido.xlsx:/tmp/arb2-corregido.xlsx:ro   api python manage.py importar_planilla /tmp/arb2-corregido.xlsx --seco   # quita --seco para escribir
```

Los dos importadores se pueden repetir sin duplicar. La planilla de la brigada **no entra al repo**: se monta desde fuera, de solo lectura. Detalle y licencias en [datos/README.md](datos/README.md). Contorno del campus © colaboradores de OpenStreetMap, ODbL.

## Documentación
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): capas del back y quién llama a quién.
- [docs/requerimientos.md](docs/requerimientos.md): qué pide el stakeholder.
