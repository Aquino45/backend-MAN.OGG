# Censo arbóreo UPeU Lima — back

API del **Censo arbóreo UPeU Lima**, sistema web del censo de árboles del campus UPeU Ñaña con un mapa dividido en sectores. Este repo es el back: Django 5 + Django REST Framework + GeoDjango sobre PostgreSQL 16 + PostGIS 3.4, en Docker. Aquí vive el contrato `contrato/openapi.yaml`, que manda sobre el front.

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

Cada árbol entra «publicado» o «en revisión» según la regla de calidad (ver abajo); el importador lista publicados, en revisión con sus motivos, duplicados no incorporados, ejemplos sin cambios y los textos de la planilla que no coinciden con una especie, un valor del catálogo, una brigada o un grupo. Los dos importadores se pueden repetir sin duplicar. La planilla de la brigada **no entra al repo**: se monta desde fuera, de solo lectura. Detalle y licencias en [datos/README.md](datos/README.md). Contorno del campus © colaboradores de OpenStreetMap, ODbL.

## Panel de administración
Mientras llega el panel propio (M2), el censo se administra en `/<ADMIN_RUTA>`. Un superusuario crea a cada persona desde «Usuarios», marca «Es staff» y la pone en un grupo:
- **Administrador:** todo sobre árboles y sectores (con su geometría), la papelera completa y la marca de ejemplo.
- **Editor:** crea y edita árboles, los ubica en el mapa, los manda a la papelera y los restaura; no elimina en definitiva, no edita sectores ni cambia la marca de ejemplo.

Nada se borra por error: «Eliminar» pide el motivo y manda el árbol a la **Papelera**, de donde se restaura (o, solo el Administrador, se elimina en definitiva). Cada cambio queda en el historial del registro, con quién, cuándo y qué cambió, y se puede volver a una versión anterior. No hay registro público.

**Calidad del registro:** un árbol vacío o inconsistente queda «en revisión»: no sale en la web, pero sí en el panel con sus motivos. El filtro «Estado del registro» de la lista de árboles los separa, la columna «Motivos de revisión» y el bloque de solo lectura del formulario dicen qué falta, y el índice avisa «N registros en revisión» con un enlace al filtro. El estado no se edita: lo recalcula la regla al guardar. Comandos (en Git Bash, con los contenedores arriba):
- `docker compose run --rm api python manage.py recalcular_calidad`: aplica la regla a todos los árboles (se corre tras `migrate` y cuando cambia el catálogo; se puede repetir).
- `docker compose run --rm api python manage.py completar_ejemplo datos/demo/completar-ejemplo-v1.json`: llena el `tipo_individuo` de los 73 árboles simulados sin pisar nada (se puede repetir).

**Cargar planilla:** Administrador y Editor (permiso `cargar_planilla`) suben el `.xlsx` de la brigada desde «Cargar planilla», en el índice del panel. Primero se valida sin guardar nada y se ve el resumen («N listos · N con campos vacíos · N inconsistentes · N duplicados»). Si hay registros inconsistentes o duplicados, una alerta pregunta si se quieren revisar: **Sí** abre una fila por registro, con el campo con problema resaltado y editable (listas con los valores activos del catálogo, números en campo numérico) y la casilla «Conservar» (desmarcada; de un código repetido se conserva solo uno); **No** avisa qué pasa con cada código y, al confirmar, incorpora solo los registros buenos. Lo conservado y completo se publica, lo conservado con problemas queda en revisión y el resultado lista los códigos de cada grupo. Solo `.xlsx` de hasta `TAMANO_MAXIMO_PLANILLA_BYTES` y `FILAS_MAXIMAS_PLANILLA` filas; el archivo no se guarda en el servidor y un lote sin decidir se descarta a las `HORAS_VIDA_LOTE_CARGA` horas. Solo quien subió el archivo puede confirmarlo. La consola (`importar_planilla`) usa los mismos pasos y no cambia.

**Especies, brigadas y grupos:** Administrador y Editor agregan, editan y ven; solo el Administrador borra.
- **Especies:** nombre científico (único), nombre común, `alias` (otros nombres con que llega en la planilla, uno por línea), familia, forma, origen (el origen de un árbol es el de su especie) y la ficha de ayuda. Se filtran por «revisada» y por forma. Al editar un árbol, la especie se busca escribiendo (también por alias). La planilla nunca crea una especie: un nombre que no coincide deja el árbol en revisión y la especie nueva se crea aquí.
- **Brigadas:** una brigada con sus grupos (nombre, integrantes, alias) en la misma pantalla.
- **Planilla:** la columna «Grupo» es opcional. «Brigada» y «Grupo» se resuelven juntos (el grupo, por nombre o alias); un grupo o una brigada que no se reconocen no mandan el árbol a revisión: la consola los lista aparte y el texto queda en el árbol. Al corregir un registro con la especie no registrada, la pantalla de revisión ofrece las especies existentes.

**Cápsulas de ayuda (el «?» de la cartilla):** Administrador y Editor agregan, editan y ven, desde el panel, dos tablas (la ficha de cada especie se edita en «Especies»); solo el Administrador borra.
- **Ayudas de los datos:** qué es cada dato, en lenguaje simple; se pueden desactivar.
- **Catálogo de valores:** qué significa cada estado de las listas de la planilla. Cada fila muestra cuántos árboles vigentes tienen exactamente ese valor y se filtra por campo.
- **Ficha de la especie:** vive en la propia especie (sección «Ficha»); la fuente es obligatoria y solo salen en la API las **publicadas** (publicar es editar la especie).
- **Valores fuera del catálogo** (botón en el catálogo): los valores que usan los árboles y el catálogo no tiene, con su campo, cuántos árboles los usan y un enlace para agregarlos. Lo que la planilla trae con otras mayúsculas («bueno») ya se resuelve al valor del catálogo («Bueno»); la vista cuenta lo que no se pudo resolver (texto guardado en `valores_originales`), tal cual vino. Solo avisa: nunca cambia ni rechaza árboles.
- **Carga inicial:** `docker compose run --rm api python manage.py cargar_capsulas datos/capsulas/capsulas-v0.json [--actualizar]`. Sin `--actualizar` solo crea lo que falta y no pisa lo editado en el panel; con él sobrescribe los textos (conserva si una ficha está publicada y si una ayuda está activa). Valida el archivo entero antes de guardar.

## Documentación
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): capas del back y quién llama a quién.
- [docs/requerimientos.md](docs/requerimientos.md): qué pide el stakeholder.
