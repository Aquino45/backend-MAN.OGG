# Arquitectura del back — MAN.OGG

Este archivo manda sobre dónde va cada cosa en `backend-MAN.OGG`. **Antes de crear un archivo, ubícalo aquí.** Si no encaja en ninguna capa, el agente se detiene y pregunta; nunca inventa una carpeta nueva.

## 1. Idea en una línea
API REST de solo lectura (v1), en capas: **controlador delgado → servicio/selector → modelo**. Django + DRF + GeoDjango sobre PostGIS. El contrato `contrato/openapi.yaml` define la forma de cada respuesta.

## 2. Equivalencias con Spring (para quien viene de Java)
| Spring | Aquí | Archivo |
|---|---|---|
| `@Entity` (JPA) | modelo de Django | `apps/<dominio>/models.py` |
| `JpaRepository` / consultas | **selector**: funciones de lectura con nombre, que devuelven QuerySets u objetos | `apps/<dominio>/selectores.py` |
| `@Service` | **servicio**: escrituras y lógica (importar, transformar) | `apps/<dominio>/servicios/<accion>.py` |
| DTO + MapStruct | **serializer** de DRF (salida = forma del contrato; entrada = validación) | `apps/<dominio>/api/serializers.py` |
| `@RestController` | vista de DRF (`APIView` o función `@api_view`) | `apps/<dominio>/api/views.py` |
| `@RequestMapping` | rutas | `apps/<dominio>/api/urls.py` |
| `@ControllerAdvice` | manejador de errores de DRF | `apps/core/excepciones.py` |
| Spring Security | permisos, throttling y middlewares | `apps/core/seguridad.py` + `config/settings.py` |
| `application.properties` | `settings.py`, que lee el `.env` | `config/settings.py` + `.env.example` |
| constantes de negocio | módulo único | `config/constantes.py` |
| Flyway / Liquibase | migraciones | `apps/<dominio>/migrations/` |
| Swagger | contrato escrito primero | `contrato/openapi.yaml` |
| JUnit + MockMvc | pytest + `APIClient` | `tests/<dominio>/` |

## 3. Árbol
```text
backend-MAN.OGG/
├── config/                    ← transversal: settings, urls raíz, constantes
│   ├── settings.py            ← todo desde el entorno; nada de valores sueltos
│   ├── urls.py                ← monta cada app bajo PREFIJO_API; el admin bajo ADMIN_RUTA
│   └── constantes.py          ← constantes de negocio (MAYÚSCULAS, con docstring)
├── apps/
│   ├── core/                  ← lo técnico y compartido
│   │   ├── api/               ← views.py, urls.py (salud)
│   │   ├── excepciones.py     ← formato único de errores
│   │   ├── seguridad.py       ← permisos y throttling por defecto
│   │   └── migrations/        ← 0001_esquema (crea el esquema de la BD)
│   └── censo/                 ← el dominio del censo
│       ├── models.py          ← Sector, Arbol
│       ├── selectores.py      ← lecturas: sectores_con_total(), arboles_de_sector(id), arbol_por_codigo(cod)
│       ├── servicios/         ← importar_sectores.py, importar_planilla.py
│       ├── api/
│       │   ├── serializers.py ← DTO de salida, con la forma exacta del contrato
│       │   ├── views.py       ← controladores delgados
│       │   └── urls.py
│       ├── admin.py
│       ├── management/commands/ ← comandos delgados que llaman a un servicio
│       └── migrations/
├── contrato/                  ← openapi.yaml + ejemplos (manda)
├── datos/                     ← polígonos versionados; la planilla real NO entra
├── db/init/                   ← SQL del primer arranque de PostGIS
├── scripts/                   ← herramientas de CI (validar_contrato.py)
├── tests/                     ← espejo de apps/: tests/core/, tests/censo/
└── docs/                      ← ARQUITECTURA (este), ESTADO, CANARIOS, tickets
```

## 4. Reglas de capas (quién puede llamar a quién)
| Capa | Puede usar | No puede |
|---|---|---|
| `api/views.py` (controlador) | selectores, servicios, serializers, permisos | tocar el ORM directo, tener lógica de negocio, armar JSON a mano |
| `api/serializers.py` (DTO) | modelos (para leer campos) | consultar la BD, llamar servicios |
| `selectores.py` (lectura) | modelos y el ORM | escribir en la BD, saber de HTTP |
| `servicios/` (escritura y lógica) | modelos, selectores, constantes | saber de HTTP (`request`, `Response`) ni imprimir; devuelven datos o un reporte |
| `models.py` | constantes | importar capas de arriba |
| `management/commands/` | servicios | tener lógica (solo argumentos → servicio → imprimir el reporte) |

- Toda coordenada se guarda en `SRID_UTM_CENSO` y se transforma a `SRID_MAPA` en el **selector**, con PostGIS (`Transform`), nunca a mano.
- Un archivo de más de ~300 líneas se parte, y cada pieza nueva viene con su test.

## 5. Receta: agregar un endpoint
1. ¿Está en el contrato? Si no, primero va un ticket de contrato, y Risc lo aprueba.
2. **Selector** en `selectores.py`, con su test en `tests/<dominio>/test_selectores.py`.
3. **Serializer** en `api/serializers.py` con la forma exacta del schema del contrato. Su test valida la salida contra el schema con `jsonschema`, igual que `scripts/validar_contrato.py`.
4. **Vista** en `api/views.py`: solo GET, valida el parámetro de ruta (por ejemplo el `codigo` con `PATRON_CODIGO_ARBOL`), llama al selector y devuelve el serializer. Un 404 sale de una excepción, que transforma `apps/core/excepciones.py`.
5. **Ruta** en `api/urls.py`, incluida desde `config/urls.py`.
6. **Test de API** con `APIClient`: 200 con la forma del contrato y 404 con `{"detail": …}`.

## 6. Seguridad mínima (sin login de usuarios en la v1)
- **API de solo lectura por defecto:** `DEFAULT_PERMISSION_CLASSES` solo permite métodos seguros (GET, HEAD, OPTIONS), aunque una vista se olvide de declararlo.
- **Throttling** para anónimos, con la tasa en `.env` (`API_LIMITE_ANONIMO`, por ejemplo `120/min`).
- **Errores:** un formato único `{"detail": "…"}` en español; nunca trazas. En producción, `DEBUG=false`.
- **Producción, desde `.env`:** `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` y `CSRF_TRUSTED_ORIGINS`.
- **CORS** con lista blanca (`CORS_ORIGENES_PERMITIDOS`) y **`ALLOWED_HOSTS`** desde `.env`.
- **Admin:** con el login propio de Django, ruta configurable (`ADMIN_RUTA`, no `admin/` fijo) y middlewares de sesión, CSRF y clickjacking activos.
- **Entradas:** todo parámetro de ruta se valida con su patrón antes de tocar la BD.
- Secretos solo en `.env`; el repo es público.

## 7. Nombres
- Python en `snake_case` y en español; constantes en `MAYÚSCULAS`.
- Los campos se llaman igual que en el contrato y llevan la unidad (`dap_cm`, `altura_total_m`).
- Selectores con nombre de lo que devuelven (`arboles_de_sector`); servicios con verbo (`importar_planilla`).

## 8. Estado actual frente al objetivo (09/10/2026)
| Pieza | Hoy | Se ajusta en |
|---|---|---|
| `apps/censo/models.py`, `servicios/`, `admin.py`, `management/` | ✅ como en el árbol (BE-003) | — |
| `apps/core/views.py` y `urls.py` (salud) | en la raíz de `core/` | BE-004: pasan a `apps/core/api/` sin cambiar la ruta |
| `tests/test_salud.py`, `test_configuracion.py`, `test_contrato.py` | en la raíz de `tests/` | BE-004: pasan a `tests/core/` |
| `selectores.py`, `api/` de censo, `excepciones.py`, `seguridad.py` | no existen | BE-004 |
| Admin en `admin/` fijo | escrito a mano en `config/urls.py` | BE-004: `ADMIN_RUTA` desde `.env` |
| 2 constantes en `importar_sectores.py` | dentro del servicio | BE-004: a `config/constantes.py` |
| `*.xlsx` en `.gitignore` | falta | DOC-002 |
