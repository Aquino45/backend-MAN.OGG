# Requerimientos — Censo arbóreo UPeU Lima (v0.2, 09/10/2026)

Fuente: la visión del stakeholder, recibida el 08/10. Se convierte en RF/RNF y Cristhian aprueba cada uno. Prioridad MoSCoW: M (debe), S (debería), C (podría), W (no ahora). **v1** = entra en la entrega del lunes 12/10. Estados: `propuesto` → `aprobado` → `en ticket` → `hecho`.

## Visión del stakeholder (literal, sin corregir)
> La pagina web tiene que ser interactiva, en donde se presente un mapa de la UPEU de ñaña, en donde este este sea partido en 5 seccciones, cuando el cursor pase por las secciones, la zona se volvera interactiva y este se resaltara q las demas, al hacer click este debe mostrar las especies de arboles que estan en la zona (5 arboles como ejemplo), en donde dichas cartillas de informacionm mostraran:
> •  Código árbol •  Sector •  Nombre común •  Nombre científico •  Condición de conservación •  Latitud •  Longitud •  Altura total (m) •  DAP (cm) •  Diámetro copa N-S (m) •  Diámetro copa E-O (m) •  Estado general •  Estado de copa •  Tronco / daños •  Raíces / base •  Interferencia / entorno •  Foto árbol •  CO₂ almacenado (kg CO₂e) •  CO₂ capturado anual (kg CO₂/año)
> Todo eso se mostrara de manera muy innovadora, claro dentro de la cartilla de informacion estara las fotos de los arboles.
> [Además, un pedido sobre la animación de entrada: ver RF-07.]
> La paleta de colores de la pagina web debe ser igual a la del arbol presetnado xdd

## Actores
- **Visitante:** cualquier persona que abre la página. Solo mira. Es el único actor de la v1.
- **Administrador del censo** (no aparece en la visión; candidato para M2): carga y edita árboles.

## Requerimientos funcionales
| ID | Requerimiento | Prioridad | v1 | Criterio de aceptación | Estado |
|---|---|---|---|---|---|
| RF-01 | Mostrar el mapa del campus UPeU Ñaña dividido en **5 sectores**. **Vista principal ilustrada** (vector con la paleta del árbol; decidido el 08/10, P1) | M | ✔ | Se ven los 5 sectores completos, sin huecos ni traslapes, con su nombre o número; el dibujo se genera desde los polígonos reales (no a mano alzada), para que coincida con RF-10 | propuesto |
| RF-02 | **Resaltar el sector al pasar el cursor**; los demás se atenúan | M | ✔ | Con el cursor encima, el sector cambia de estilo (color o elevación) y los otros 4 bajan de opacidad. Al salir, todo vuelve al estado normal. En pantallas táctiles, el primer toque resalta | propuesto |
| RF-03 | **Click en un sector:** mostrar los árboles de ese sector | M | ✔ | Se abre un panel con los árboles del sector (mínimo 5 por sector en la v1, 25 en total) y cada uno se puede abrir | propuesto |
| RF-04 | **Cartilla del árbol** con los 18 campos de datos más la foto (ver «Datos por árbol») | M | ✔ | Muestra los 18 campos con su unidad y la foto real. Un campo vacío dice «Sin dato»; nunca se inventa | propuesto |
| RF-05 | Presentación **«muy innovadora»** de la cartilla y del mapa | M | ✔ | Transiciones animadas al entrar a un sector y al abrir una cartilla. La foto es la protagonista. Altura, DAP, copa y CO₂ se muestran con indicadores visuales, no solo texto. Cristhian lo aprueba con capturas | propuesto |
| RF-06 | Mostrar el **CO₂ almacenado** (kg CO₂e) y el **CO₂ capturado anual** (kg CO₂/año) de cada árbol | M | ✔ | El valor lo calcula el stakeholder en gabinete y llega en el Excel; el sistema solo lo muestra, nunca lo calcula. Si falta, la cartilla dice «Sin dato» (decidido el 08/10, P2) | propuesto |
| RF-07 | **Animación de entrada con variantes** (decidido el 08/10, P3) | S | ✔ | La entrada al mapa elige su variante con `elegirVariante` y una tabla de pesos de `constantes.ts`; cada carga se sortea de nuevo y el test inyecta el aleatorio. Una variante que no es la estándar se descarga solo cuando sale, dura unos segundos y después entra la ruta pedida, sin cambiar la URL | propuesto |
| RF-08 | **La paleta de la página es la del árbol** que dio el stakeholder | M | ✔ | Tokens de color tomados de esa ilustración (ver «Paleta»). No hay colores de marca fuera de ellos, salvo los neutros necesarios para leer el texto | propuesto |
| RF-09 | Ubicar cada árbol como **punto** dentro de su sector (lat/lon) | S | ✔ | Al entrar a un sector se ven sus árboles en su posición real; un click en el punto abre su cartilla | propuesto |
| RF-10 | Botón para ver los sectores sobre un **mapa real** (satélite o calles), además de la vista ilustrada (decidido el 08/10, P1) | S | — | Un toggle cambia entre ilustrado y real; los 5 sectores y los árboles caen en el mismo lugar en ambas vistas. Entra a la v1 solo si sobra tiempo | propuesto |
| RF-11 | Registro y edición de árboles por un administrador | W | — | No está en la visión; candidato para M2 | propuesto |
| RF-12 | **Módulo web de carga de datos desde la planilla Excel** (pedido de Cristhian, 09/10) | S | — | Un administrador sube `arb2-corregido.xlsx` (u otra hoja con el mismo formato) y el sistema muestra, **antes de guardar**, el reporte de validación y limpieza: números no válidos (p. ej. «muerto» en el DAP), valores fuera de catálogo, árboles fuera de su sector y códigos calculados. Después confirma o cancela. Reusa el servicio que importa la planilla (ETL v0). No se pierde ningún dato: lo que no es válido va a `observaciones` y al reporte. Candidato para M2 | propuesto |

## Requerimientos no funcionales
| ID | Requerimiento | Prioridad | Medida |
|---|---|---|---|
| RNF-01 | Responsive | M | Se usa bien a 360 px (celular) y a 1440 px (laptop). En el celular, el panel de la cartilla pasa a ser una hoja inferior |
| RNF-02 | Rendimiento | M | Carga inicial < 3 s en 4G. Fotos en WebP, con miniatura y tamaño completo. Las variantes de la entrada que no son la estándar se descargan solo cuando salen |
| RNF-03 | Legibilidad con la paleta | M | Contraste del texto ≥ 4.5:1 (WCAG AA). El carmín sobre el azul noche da 3.32:1: sirve para títulos grandes y acentos, no para párrafos. El texto va en un neutro claro sobre el azul noche (15.6:1 con blanco) |
| RNF-04 | Veracidad de los datos | M | Ningún dato inventado. Cada árbol lleva `fuente` (planilla o foto de campo). Los datos de prueba van solo en fixtures, con `demo: true` |
| RNF-05 | Coordenadas | M | Lat/lon en WGS84 (EPSG:4326). Si vienen en UTM, se convierten en la BD con PostGIS, nunca a mano |
| RNF-06 | Navegadores | S | Las 2 últimas versiones de Chrome, Edge, Firefox y Safari (incluido el móvil) |
| RNF-07 | Accesibilidad | S | Los sectores se recorren también con teclado (Tab y Enter) y tienen nombre accesible. Se respeta `prefers-reduced-motion` |
| RNF-08 | Repos públicos | M | Nada de `.env`, claves ni datos personales en git |

## Datos por árbol (contrato de la cartilla)
| # | Campo (visión) | Campo de la API | Tipo | Unidad |
|---|---|---|---|---|
| 1 | Código árbol | `codigo` | texto (`S01-A001`) | — |
| 2 | Sector | `sector` | referencia al sector (1–5) | — |
| 3 | Nombre común | `nombre_comun` | texto | — |
| 4 | Nombre científico | `nombre_cientifico` | texto (en cursiva en la UI) | — |
| 5 | Condición de conservación | `condicion_conservacion` | catálogo (pregunta P4) | — |
| 6 | Latitud | `lat` | decimal (6 decimales) | ° WGS84 |
| 7 | Longitud | `lon` | decimal (6 decimales) | ° WGS84 |
| 8 | Altura total | `altura_total_m` | decimal | m |
| 9 | DAP | `dap_cm` | decimal | cm |
| 10 | Diámetro de copa N-S | `copa_ns_m` | decimal | m |
| 11 | Diámetro de copa E-O | `copa_eo_m` | decimal | m |
| 12 | Estado general | `estado_general` | catálogo (bueno / regular / malo…) | — |
| 13 | Estado de copa | `estado_copa` | texto o catálogo | — |
| 14 | Tronco / daños | `tronco_danos` | texto o catálogo | — |
| 15 | Raíces / base | `raices_base` | texto o catálogo | — |
| 16 | Interferencia / entorno | `interferencia_entorno` | texto o catálogo | — |
| 17 | Foto del árbol | `foto_url` (+ `foto_miniatura_url`) | imagen | — |
| 18 | CO₂ almacenado | `co2_almacenado_kg` | decimal | kg CO₂e |
| 19 | CO₂ capturado anual | `co2_captura_anual_kg` | decimal | kg CO₂/año |
| + | (trazabilidad) | `fuente`, `fecha_registro` | texto, fecha | — |

Sector: `id` (1–5), `nombre`, `geom` (polígono) y `color` (token de la paleta).

## Paleta (extraída por script el 08/10 de la ilustración del árbol que dio el stakeholder)
| Token propuesto | Hex | % de píxeles | Uso sugerido |
|---|---|---|---|
| `--copa-carmin` | `#e02040` | 58.3 | Acento principal, sector resaltado, botones |
| `--copa-magenta-oscuro` | `#a00080` | 21.1 | Sectores en reposo, bordes |
| `--copa-magenta` | `#c00080` | 12.2 | Estados secundarios, chips |
| `--tronco-noche` | `#202040` | 8.2 | Fondo principal (tema oscuro) |
| `--sombra-violeta` | `#413e59` | 0.1 | Superficies y paneles |
| (neutro de lectura, por definir) | p. ej. `#f6eef2` | — | Texto sobre el fondo noche |

## Preguntas abiertas
| ID | Pregunta | Para quién | Bloquea |
|---|---|---|---|
| P1 | ~~¿Mapa real, ilustrado o los dos?~~ **Resuelta el 08/10:** ilustrado como vista principal + mapa real opcional | Cristhian | — |
| P2 | ~~¿Quién calcula el CO₂?~~ **Resuelta el 08/10:** el stakeholder, en gabinete; el sistema solo lo muestra | Cristhian | — |
| P3 | ~~Animación de entrada~~ **Resuelta el 08/10:** ver RF-07 | Cristhian | — |
| P4 | ~~¿Según qué lista?~~ **Resuelta el 08/10:** lista peruana DS 043-2006-AG; la llena el stakeholder, con fuente | Cristhian | — |
| P5 | ~~Límites de los 5 sectores~~ **Resuelta provisionalmente el 08/10:** S1 desde el croquis y S2–S5 propuestos por el equipo; aprobados por Cristhian y el stakeholder, sujetos a cambios (`datos/sectores/`) | Cristhian | — |
| P6 | Datos de los 25 árboles: **al 08/10 hay datos parciales de 1 solo sector**; el resto se recolecta en Excel (pendiente). ¿Cuándo llega la planilla y con qué columnas? | Cristhian / equipo de campo | toda la v1 |
| P7 | ~~«Caso PUEM»~~ Descartada: era una frase suelta del 08/10, no un requisito | — | — |

## Riesgo de la v1 (lunes 12/10)
- Solo hay datos de 1 de los 5 sectores. Plan: la planilla Excel con las 19 columnas de «Datos por árbol» es el formato de entrada. La v1 muestra datos reales donde existan y, en los demás sectores, árboles **demo** marcados como tales en la cartilla («Dato de ejemplo»), nunca mezclados ni presentados como reales. Cuando llegue la planilla, se importa y los demo se borran.
