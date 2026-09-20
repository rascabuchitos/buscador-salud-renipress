# Buscador de establecimientos de salud (RENIPRESS)

Sitio estático (sin backend) que indexa el Registro Nacional de IPRESS
(RENIPRESS, SUSALUD) para búsqueda por código o nombre en el navegador.

## Actualización automática

`.github/workflows/build.yml` corre todos los días:
1. `build/download_and_check.py` descarga el CSV oficial y compara su hash
   contra la última corrida.
2. Si cambió, `build/shard.py` reconstruye `web/dist/`.
3. Se publica por FTP a mariopastor.pro.

Fuente: datosabiertos.gob.pe (RENIPRESS/SUSALUD) — licencia ODC-BY.
