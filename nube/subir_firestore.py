"""Sube un CSV de lecturas a Cloud Firestore (Etapa 3).

Requisitos:
    pip install firebase-admin
    Una clave de cuenta de servicio: Consola de Firebase -> Configuración del
    proyecto -> Cuentas de servicio -> "Generar nueva clave privada".
    Guárdela como nube/clave_servicio.json. NUNCA la suba a GitHub
    (ya está en .gitignore).

Uso:
    # 1. Siempre primero en seco: no escribe nada, muestra qué subiría.
    python subir_firestore.py ../datos/muestra.csv --seco

    # 2. Subir de verdad.
    python subir_firestore.py ../datos/muestra.csv

    # Borrar la colección antes de subir (p. ej. cambiar la muestra por los datos finales).
    python subir_firestore.py ../datos/colmena_final.csv --vaciar

Qué hace:
  - Lee la fecha de la columna --col-fecha. Si viene sin zona horaria, la toma como
    hora de Costa Rica (UTC-6) y la guarda en Firestore como Timestamp.
  - Reduce las filas "aumentado" a una cada --cada-min minutos (5 por defecto).
    Las filas "real" se suben todas.
  - El id de cada documento sale de la fecha (UTC), así que volver a subir el
    mismo CSV sobrescribe en vez de duplicar.
  - Se niega a pasar de --max-escrituras (18 000) para no agotar la cuota gratuita
    de 20 000 escrituras por día.
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CR = timezone(timedelta(hours=-6))
SENSORES = ["temp_int", "temp_ext", "peso", "actividad", "gas", "luz"]
ENTEROS = {"actividad", "gas", "luz"}
LOTE = 400  # Firestore permite hasta 500 operaciones por lote


def leer_fecha(texto: str) -> datetime:
    texto = texto.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.fromisoformat(texto) if fmt is None else datetime.strptime(texto, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Fecha no reconocida: {texto!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CR)
    return dt.astimezone(timezone.utc)


def a_numero(campo: str, texto: str):
    texto = (texto or "").strip()
    if texto == "":
        return None
    v = float(texto)
    return int(round(v)) if campo in ENTEROS else v


def preparar(ruta: Path, col_fecha: str, cada_min: int):
    docs, vistos_bucket, omitidas = {}, set(), 0
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        faltan = [c for c in [col_fecha, *SENSORES] if c not in (lector.fieldnames or [])]
        if faltan:
            sys.exit(f"ERROR: al CSV le faltan columnas {faltan}. Tiene: {lector.fieldnames}\n"
                     f"Ver CONTRATO_DATOS.md o use --col-fecha.")
        for n, fila in enumerate(lector, start=2):
            try:
                ts = leer_fecha(fila[col_fecha])
            except ValueError as e:
                sys.exit(f"ERROR en la línea {n}: {e}")
            origen = (fila.get("origen") or "real").strip() or "real"
            if origen != "real" and cada_min > 0:
                bucket = int(ts.timestamp()) // (cada_min * 60)
                if bucket in vistos_bucket:
                    omitidas += 1
                    continue
                vistos_bucket.add(bucket)
            doc = {"ts": ts, "origen": origen}
            for c in SENSORES:
                doc[c] = a_numero(c, fila[c])
            # Columnas extra de A (periodo, estado, alerta...): se suben tal cual.
            for c, v in fila.items():
                if c in doc or c == col_fecha or c is None:
                    continue
                try:
                    doc[c] = float(v) if v not in ("", None) else None
                except ValueError:
                    doc[c] = v
            docs[ts.strftime("%Y%m%dT%H%M%S")] = doc
    return docs, omitidas


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path)
    p.add_argument("--clave", type=Path, default=Path(__file__).resolve().parent / "clave_servicio.json")
    p.add_argument("--coleccion", default="lecturas")
    p.add_argument("--col-fecha", default="fecha_hora")
    p.add_argument("--cada-min", type=int, default=5, help="0 = no reducir")
    p.add_argument("--max-escrituras", type=int, default=18000)
    p.add_argument("--vaciar", action="store_true", help="borra la colección antes de subir")
    p.add_argument("--seco", action="store_true", help="no escribe; solo muestra el resumen")
    a = p.parse_args()

    docs, omitidas = preparar(a.csv, a.col_fecha, a.cada_min)
    if not docs:
        sys.exit("El CSV no tiene filas.")
    tss = sorted(d["ts"] for d in docs.values())
    por_origen = {}
    for d in docs.values():
        por_origen[d["origen"]] = por_origen.get(d["origen"], 0) + 1

    print(f"Archivo: {a.csv}")
    print(f"Documentos a subir: {len(docs)}  {por_origen}  (omitidas por reducción: {omitidas})")
    print(f"Desde {tss[0].astimezone(CR):%d/%m/%Y %H:%M} hasta {tss[-1].astimezone(CR):%d/%m/%Y %H:%M} (hora CR)")
    print("Ejemplo:", next(iter(docs.items())))

    if a.seco:
        print("\nModo en seco: no se escribió nada.")
        return

    import firebase_admin
    from firebase_admin import credentials, firestore

    if not a.clave.exists():
        sys.exit(f"ERROR: no encuentro la clave {a.clave}. Ver instrucciones arriba del archivo.")
    firebase_admin.initialize_app(credentials.Certificate(str(a.clave)))
    db = firestore.client()
    col = db.collection(a.coleccion)

    escrituras = 0
    if a.vaciar:
        ids = [d.id for d in col.select([]).stream()]
        escrituras += len(ids)
        if escrituras + len(docs) > a.max_escrituras:
            sys.exit(f"ERROR: vaciar ({len(ids)}) + subir ({len(docs)}) supera --max-escrituras.")
        for i in range(0, len(ids), LOTE):
            lote = db.batch()
            for doc_id in ids[i:i + LOTE]:
                lote.delete(col.document(doc_id))
            lote.commit()
        print(f"Borrados {len(ids)} documentos de '{a.coleccion}'.")

    if escrituras + len(docs) > a.max_escrituras:
        sys.exit(f"ERROR: {len(docs)} escrituras supera --max-escrituras={a.max_escrituras}. "
                 f"Suba más reducido (--cada-min) o en dos días.")

    items = list(docs.items())
    for i in range(0, len(items), LOTE):
        lote = db.batch()
        for doc_id, d in items[i:i + LOTE]:
            lote.set(col.document(doc_id), d)
        lote.commit()
        print(f"  {min(i + LOTE, len(items))}/{len(items)}")
    print(f"Listo: {len(items)} documentos en '{a.coleccion}'.")


if __name__ == "__main__":
    main()
