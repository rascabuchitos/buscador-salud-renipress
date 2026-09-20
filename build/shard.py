"""
Genera dist/ a partir de data/establecimientos.csv (esquema REAL de RENIPRESS/SUSALUD,
CSV separado por ';', con las columnas oficiales del dataset).

  dist/shards/{n}.tsv.gz     -> índice core, shardeado por codigo % SHARD_COUNT
  dist/search-index.json.gz  -> índice de nombres para TODOS los registros
  dist/meta.json             -> metadata del build (incluye fuente y fecha)
"""
import csv
import gzip
import json
import pathlib
import datetime

SHARD_COUNT = 128
ROOT = pathlib.Path(__file__).parent.parent
SRC = ROOT / "data" / "establecimientos.csv"
DIST = ROOT / "web" / "dist"

# Columnas reales del CSV oficial de RENIPRESS (separador ';')
CAMPOS_SHARD = [
    "COD_IPRESS", "NOMBRE", "INSTITUCION", "CLASIFICACION",
    "TIPO_ESTABLECIMIENTO", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
    "DIRECCION", "CATEGORIA", "TELEFONO", "ESTADO", "CONDICION",
]


def load_rows():
    with SRC.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def build_shards(rows):
    shard_dir = DIST / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    buckets = {i: [] for i in range(SHARD_COUNT)}

    for r in rows:
        codigo = int(r["COD_IPRESS"])
        shard_id = codigo % SHARD_COUNT
        line = "\t".join(r[campo].strip() for campo in CAMPOS_SHARD)
        buckets[shard_id].append(line)

    for shard_id, lines in buckets.items():
        content = "\n".join(lines).encode("utf-8")
        path = shard_dir / f"{shard_id}.tsv.gz"
        with gzip.open(path, "wb", compresslevel=9) as f:
            f.write(content)

    return {k: len(v) for k, v in buckets.items()}


def normalize(s):
    repl = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return s.translate(repl).lower().strip()


def build_search_index(rows):
    DIST.mkdir(parents=True, exist_ok=True)
    entries = []
    for r in rows:
        if not r["NOMBRE"].strip():
            continue  # 17 registros sin nombre en el dataset real, se omiten del índice
        entries.append({
            "c": int(r["COD_IPRESS"]),
            "n": r["NOMBRE"].strip(),
            "n_n": normalize(r["NOMBRE"]),
            "d": r["DISTRITO"].strip(),
            "dep": r["DEPARTAMENTO"].strip(),
            "cond": (r["CONDICION"].strip() or r["ESTADO"].strip()),
        })
    payload = json.dumps(entries, ensure_ascii=False).encode("utf-8")
    out_path = DIST / "search-index.json.gz"
    with gzip.open(out_path, "wb", compresslevel=9) as f:
        f.write(payload)
    return len(entries), out_path.stat().st_size


def build_meta(shard_sizes, record_count, index_bytes, source_note):
    meta = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "shard_count": SHARD_COUNT,
        "record_count": record_count,
        "search_index_bytes_gz": index_bytes,
        "source": source_note,
    }
    with (DIST / "meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


if __name__ == "__main__":
    rows = load_rows()
    sizes = build_shards(rows)
    n, idx_bytes = build_search_index(rows)
    source_note = (
        "RENIPRESS - Registro Nacional de IPRESS, SUSALUD. "
        "Datos abiertos bajo licencia Open Data Commons Attribution (ODC-BY). "
        "https://www.datosabiertos.gob.pe/dataset/registro-nacional-de-ipress-renipress-superintendencia-nacional-de-salud-susalud"
    )
    meta = build_meta(sizes, len(rows), idx_bytes, source_note)
    print(f"{len(rows)} registros -> {SHARD_COUNT} shards")
    print(f"search-index.json.gz: {idx_bytes/1024:.1f} KB comprimido")
    print(meta)
