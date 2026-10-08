# Requerimientos — MAN.OGG (v0.1, 08/10/2026, 18:10 Lima)

Fuente: la visión del stakeholder, recibida el 08/10 (original en `contexto/fuentes/vision-stakeholder-2026-10-08.txt`). El asesor la convierte en RF/RNF y Cristhian aprueba cada uno. Prioridad MoSCoW: M (debe), S (debería), C (podría), W (no ahora). **v1** = entra en la entrega del lunes 12/10. Estados: `propuesto` → `aprobado` → `en ticket` → `hecho`.

## Visión del stakeholder (literal, sin corregir)
> La pagina web tiene que ser interactiva, en donde se presente un mapa de la UPEU de ñaña, en donde este este sea partido en 5 seccciones, cuando el cursor pase por las secciones, la zona se volvera interactiva y este se resaltara q las demas, al hacer click este debe mostrar las especies de arboles que estan en la zona (5 arboles como ejemplo), en donde dichas cartillas de informacionm mostraran:
> •  Código árbol •  Sector •  Nombre común •  Nombre científico •  Condición de conservación •  Latitud •  Longitud •  Altura total (m) •  DAP (cm) •  Diámetro copa N-S (m) •  Diámetro copa E-O (m) •  Estado general •  Estado de copa •  Tronco / daños •  Raíces / base •  Interferencia / entorno •  Foto árbol •  CO₂ almacenado (kg CO₂e) •  CO₂ capturado anual (kg CO₂/año)
> Todo eso se mostrara de manera muy innovadora, claro dentro de la cartilla de informacion estara las fotos de los arboles.
> Tambien queiro agragar como un easter egg, en donde cuando se carge una pagina web aparezca el gitf del arbol q te subi, este easter egg debe tener una probabilidad de 1 en 999 q aparezca, este desaparecera cuando se recargue la pagina y debe redireccionarse a donde se debia
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
| RF-06 | Mostrar el **CO₂ almacenado** (kg CO₂e) y el **CO₂ capturado anual** (kg CO₂/año) de cada árbol | M | ✔ | Cada valor tiene su fuente o su método de cálculo documentado (ver pregunta P2) | propuesto |
| RF-07 | **Easter egg:** al cargar la página, con probabilidad **1 en 999**, aparece el GIF del árbol como intro de unos segundos y luego sigue solo a la página pedida (decidido el 08/10, P3) | S | ✔ | Cada carga evalúa `Math.random() < 1/999`; el test lo prueba con el azar inyectado. Si sale, el GIF se muestra a pantalla completa ~3 s (≈ 1 vuelta de 21 cuadros × 120 ms, redondeada) y después entra la ruta que se pidió, sin cambiar la URL. Si no sale, el GIF ni siquiera se descarga. Al recargar se vuelve a sortear | propuesto |
| RF-08 | **La paleta de la página es la del árbol** del GIF | M | ✔ | Tokens de color tomados del GIF (ver «Paleta»). No hay colores de marca fuera de ellos, salvo los neutros necesarios para leer el texto | propuesto |
| RF-09 | Ubicar cada árbol como **punto** dentro de su sector (lat/lon) | S | ✔ | Al entrar a un sector se ven sus árboles en su posición real; un click en el punto abre su cartilla | propuesto |
| RF-10 | Botón para ver los sectores sobre un **mapa real** (satélite o calles), además de la vista ilustrada (decidido el 08/10, P1) | S | — | Un toggle cambia entre ilustrado y real; los 5 sectores y los árboles caen en el mismo lugar en ambas vistas. Entra a la v1 solo si sobra tiempo | propuesto |
| RF-11 | Registro y edición de árboles por un administrador | W | — | No está en la visión; candidato para M2 | propuesto |

## Requerimientos no funcionales
| ID | Requerimiento | Prioridad | Medida |
|---|---|---|---|
| RNF-01 | Responsive | M | Se usa bien a 360 px (celular) y a 1440 px (laptop). En el celular, el panel de la cartilla pasa a ser una hoja inferior |
| RNF-02 | Rendimiento | M | Carga inicial < 3 s en 4G. Fotos en WebP, con miniatura y tamaño completo. El GIF solo se descarga si sale el easter egg |
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

## Paleta (extraída del GIF por script el 08/10; 212×182 px, 21 cuadros de 120 ms, en bucle)
| Token propuesto | Hex | % de píxeles | Uso sugerido |
|---|---|---|---|
| `--copa-carmin` | `#e02040` | 58.3 | Acento principal, sector resaltado, botones |
| `--copa-magenta-oscuro` | `#a00080` | 21.1 | Sectores en reposo, bordes |
| `--copa-magenta` | `#c00080` | 12.2 | Estados secundarios, chips |
| `--tronco-noche` | `#202040` | 8.2 | Fondo principal (tema oscuro) |
| `--sombra-violeta` | `#413e59` | 0.1 | Superficies y paneles |
| (neutro de lectura, por definir) | p. ej. `#f6eef2` | — | Texto sobre el fondo noche |

El GIF original está en `assets/arbol-easter-egg.gif`. Queda fuera de los repos hasta el ticket del front que lo use.

## Preguntas abiertas
| ID | Pregunta | Para quién | Bloquea |
|---|---|---|---|
| P1 | ~~¿Mapa real, ilustrado o los dos?~~ **Resuelta el 08/10:** ilustrado como vista principal + mapa real opcional | Cristhian | — |
| P2 | ¿El CO₂ ya viene calculado en la planilla o lo calcula el sistema (ecuación alométrica con DAP, altura y densidad de la madera)? | stakeholder | RF-06 |
| P3 | ~~¿El GIF se queda hasta recargar o dura unos segundos?~~ **Resuelta el 08/10:** intro de unos segundos y luego sigue solo a la página pedida | Cristhian | — |
| P4 | Condición de conservación: ¿según qué lista (UICN, DS 043-2006-AG del Perú, CITES) o texto libre? | stakeholder | RF-04 |
| P5 | ¿Quién define los límites de los 5 sectores, y en qué formato (KML, plano, dibujo sobre el mapa)? | stakeholder | RF-01 |
| P6 | Datos de los 25 árboles: **al 08/10 hay datos parciales de 1 solo sector**; el resto se recolecta en Excel (pendiente). ¿Cuándo llega la planilla y con qué columnas? | Cristhian / equipo de campo | toda la v1 |
| P7 | «Caso PUEM»: ¿qué es? | Cristhian | glosario |

## Riesgo de la v1 (lunes 12/10)
- Solo hay datos de 1 de los 5 sectores. Plan: la planilla Excel con las 19 columnas de «Datos por árbol» es el formato de entrada. La v1 muestra datos reales donde existan y, en los demás sectores, árboles **demo** marcados como tales en la cartilla («Dato de ejemplo»), nunca mezclados ni presentados como reales. Cuando llegue la planilla, se importa y los demo se borran.
