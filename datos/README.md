# Datos del repo

Aquí solo viven los datos que **pueden ser públicos**. Los repos de MAN.OGG son públicos.

## `sectores/sectores-utm18s-v0.geojson`
- **Qué es:** los 5 sectores del campus UPeU Ñaña, en UTM 18S (EPSG:32718). S2 a S5 llevan `provisional: true`.
- **Origen:** croquis de la zona 1 (foto del plano del campus, 08/10/2026), georreferenciado con 4 puntos de control (error de 5 a 11 m). El límite exterior sale del contorno del campus en OpenStreetMap (way 701396579).
- **Copia literal** del archivo de `MAN.OGG-contexto`. SHA-256: `a6d817ff6eb0a345b49df24a87d97e2918263f7eb2d2052f3a982fd135a645b1`.
- **Licencia:** Contorno del campus © colaboradores de OpenStreetMap, licencia ODbL (https://www.openstreetmap.org/copyright).
- **Cargarlo:** `docker compose run --rm api python manage.py importar_sectores datos/sectores/sectores-utm18s-v0.geojson`

## La planilla de la brigada NO entra al repo
`arb2-corregido.xlsx` (hoja `Registro_Campo`) son datos crudos del censo. Nunca se copia ni se sube aquí.
Se importa por una ruta local, montándola de solo lectura en el contenedor:

```
MSYS_NO_PATHCONV=1 docker compose run --rm -v /ruta/local/arb2-corregido.xlsx:/tmp/arb2-corregido.xlsx:ro api python manage.py importar_planilla /tmp/arb2-corregido.xlsx --seco
```

Quita `--seco` para escribir en la BD. Importa antes los sectores. Monta el archivo **con su nombre real**: la `fuente` de cada árbol lo cita.
