-- Se ejecuta solo la PRIMERA vez que se crea el volumen de datos.
-- Habilita las extensiones espaciales y crea el esquema del censo.

CREATE EXTENSION IF NOT EXISTS postgis;           -- geometrías: puntos (árboles), polígonos (zonas)
CREATE EXTENSION IF NOT EXISTS postgis_topology;  -- zonas vecinas sin huecos ni traslapes
CREATE EXTENSION IF NOT EXISTS pg_trgm;           -- búsqueda por nombre de especie tolerante a errores

CREATE SCHEMA IF NOT EXISTS censo;
COMMENT ON SCHEMA censo IS 'Censo arbóreo: zonas, árboles y mediciones. Las tablas se definen al cerrar requerimientos.';

-- Nota sobre coordenadas: las fotos NoteCam vienen en UTM (WGS84).
--   Zona 17S -> SRID 32717 | 18S -> 32718 | 19S -> 32719
-- Se guardan en su SRID UTM original y se transforman a 4326 (lat/lon) para el mapa web.
