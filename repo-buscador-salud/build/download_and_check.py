"""
Descarga el CSV oficial de RENIPRESS y detecta si cambió desde la última corrida.

Flujo:
  1. Consulta la metadata del dataset en datosabiertos.gob.pe (con User-Agent de
     navegador, porque su WAF bloquea peticiones sin cabeceras "normales").
  2. De ahí saca el id del recurso real en datos.susalud.gob.pe y pregunta por
     su URL de descarga actual.
  3. Descarga el CSV, calcula su hash.
  4. Si el hash es igual al de la última corrida guardada (build/.last_hash.txt),
     no hace nada (changed=false). Si cambió, guarda el CSV en data/establecimientos.csv
     y actualiza el hash (changed=true) para que el workflow reconstruya y publique.

Si la fuente no responde (caída temporal, bloqueo de red), NO rompe el sitio:
solo se marca changed=false y se deja el sitio como estaba.
"""
import hashlib
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HASH_FILE = os.path.join(ROOT, "build", ".last_hash.txt")
CSV_OUT = os.path.join(ROOT, "data", "establecimientos.csv")

PACKAGE_API = (
    "https://www.datosabiertos.gob.pe/api/3/action/package_show"
    "?id=6a7b4b5a-edf1-43c6-84dd-1e4fe0294de4"
)
RENIPRESS_RESOURCE_ID = "8bb014bd-bb39-40d8-bfd7-0c8bcb4eb37d"
SUSALUD_RESOURCE_API = (
    f"http://datos.susalud.gob.pe/api/3/action/resource_show?id={RENIPRESS_RESOURCE_ID}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/csv, */*",
}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_csv_url():
    """Devuelve la URL de descarga actual del CSV, consultando la API de SUSALUD.
    Si eso falla, intenta usar la URL conocida como respaldo."""
    try:
        data = json.loads(fetch(SUSALUD_RESOURCE_API))
        url = data["result"]["url"]
        print(f"URL de descarga obtenida vía API: {url}")
        return url
    except Exception as e:
        print(f"[aviso] No se pudo consultar la API de SUSALUD: {e}")
        return None


def set_output(name, value):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"(local) {name}={value}")


def main():
    url = get_csv_url()
    if not url:
        print("No se pudo determinar la URL del CSV. Se omite esta corrida sin tocar el sitio.")
        set_output("changed", "false")
        return 0

    try:
        content = fetch(url, timeout=60)
    except Exception as e:
        print(f"[aviso] No se pudo descargar el CSV ({e}). Se omite esta corrida sin tocar el sitio.")
        set_output("changed", "false")
        return 0

    new_hash = hashlib.sha256(content).hexdigest()
    old_hash = None
    if os.path.exists(HASH_FILE):
        old_hash = open(HASH_FILE, encoding="utf-8").read().strip()

    if new_hash == old_hash:
        print("Sin cambios respecto a la última corrida.")
        set_output("changed", "false")
        return 0

    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    with open(CSV_OUT, "wb") as f:
        f.write(content)
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        f.write(new_hash)

    print(f"Nuevo CSV detectado y guardado ({len(content)/1024:.1f} KB).")
    set_output("changed", "true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
