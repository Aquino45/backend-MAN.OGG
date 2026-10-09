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

## Documentación
- [AGENTS.md](AGENTS.md): reglas del repo (también para Claude Code, vía [CLAUDE.md](CLAUDE.md)).
- [CONTRIBUTING.md](CONTRIBUTING.md): cómo dejar tu PC lista y el flujo diario.
- [docs/ESTADO.md](docs/ESTADO.md): estado actual y siguiente ticket.
- [docs/requerimientos.md](docs/requerimientos.md): qué pide el stakeholder.
- [docs/CANARIOS.md](docs/CANARIOS.md): registro de canarios.
- [docs/tickets/](docs/tickets/): un archivo por ticket.
