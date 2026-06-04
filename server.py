    #!/usr/bin/env python3
"""
Kizeo Forms MCP Server — HTTP transport
Deploy en Render.com y registrar como conector en claude.ai
"""

import os
import json
import urllib.request
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

# ── Configuración ──────────────────────────────────────────────────────────────
KIZEO_TOKEN = os.environ["KIZEO_TOKEN"]          # Token de la API de Kizeo
BASE_URL = "https://www.kizeoforms.com/rest/v3"
PORT = int(os.environ.get("PORT", 8000))

mcp = FastMCP(
    "kizeo",
    host="0.0.0.0",
    port=PORT,
    instructions=(
        "Herramientas para consultar formularios y registros de Kizeo Forms. "
        "Úsalas cuando el usuario pida datos de supervisiones, inducciones, EPP, "
        "mantenciones, o cualquier formulario de Kizeo."
    )
)

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url, headers={"Authorization": KIZEO_TOKEN, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _post(path: str, body: dict) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": KIZEO_TOKEN, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

# ── Herramientas ───────────────────────────────────────────────────────────────

@mcp.tool()
def list_forms() -> str:
    """Lista todos los formularios de Kizeo agrupados por categoría."""
    forms = _get("/forms").get("forms", [])
    by_class: dict = {}
    for f in forms:
        by_class.setdefault(f.get("class", "Sin categoría"), []).append(f)
    lines = [f"Total: {len(forms)} formularios\n"]
    for cat, items in sorted(by_class.items()):
        lines.append(f"## {cat}")
        for f in items:
            lines.append(f"  [{f['id']}] {f['name']}  (actualizado: {f['update_time']})")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_form_records(
    form_id: str,
    limit: int = 20,
    since_date: str = None,
    user_name: str = None
) -> str:
    """
    Obtiene los registros más recientes de un formulario.

    Args:
        form_id: ID del formulario (obtenido con list_forms)
        limit: Máximo de registros a retornar (máx. 100)
        since_date: Filtrar desde esta fecha (YYYY-MM-DD)
        user_name: Filtrar por nombre de usuario
    """
    filters = []
    if since_date:
        filters.append({"field": "answer_time", "operator": ">=", "type": "datetime", "val": since_date})
    if user_name:
        filters.append({"field": "_user_name", "operator": "like", "type": "string", "val": f"%{user_name}%"})
    body = {
        "filters": filters,
        "order": [{"col": "_update_time", "type": "desc"}],
        "number_of_data": min(int(limit), 100)
    }
    records = _post(f"/forms/{form_id}/data/advanced", body).get("data", [])
    if not records:
        return f"No se encontraron registros en el formulario {form_id}."
    lines = [f"Formulario {form_id} — {len(records)} registros:\n"]
    for r in records:
        lines.append(_fmt(r))
    return "\n".join(lines)


@mcp.tool()
def get_record(form_id: str, record_id: str) -> str:
    """
    Obtiene el detalle completo de un registro específico.

    Args:
        form_id: ID del formulario
        record_id: ID del registro
    """
    record = _get(f"/forms/{form_id}/data/{record_id}").get("data", {})
    lines = [f"# Registro {record_id} — Formulario {form_id}\n"]
    for k, v in record.items():
        if k.startswith("_"):
            lines.append(f"**{k}**: {v}")
    lines.append("")
    for k, v in record.items():
        if not k.startswith("_") and v not in (None, "", [], {}):
            val = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            lines.append(f"**{k}**: {val}")
    return "\n".join(lines)


@mcp.tool()
def search_records(form_id: str, field: str, value: str, limit: int = 20) -> str:
    """
    Busca registros donde un campo contiene un valor.

    Args:
        form_id: ID del formulario
        field: Campo a buscar (ej: '_user_name', 'rut', 'nombre')
        value: Valor a buscar (búsqueda parcial)
        limit: Máximo de resultados
    """
    body = {
        "filters": [{"field": field, "operator": "like", "type": "string", "val": f"%{value}%"}],
        "order": [{"col": "_update_time", "type": "desc"}],
        "number_of_data": min(int(limit), 100)
    }
    records = _post(f"/forms/{form_id}/data/advanced", body).get("data", [])
    if not records:
        return f"No se encontraron registros donde '{field}' contenga '{value}'."
    lines = [f"Búsqueda '{field}' ≈ '{value}' — {len(records)} resultado(s):\n"]
    for r in records:
        lines.append(_fmt(r))
    return "\n".join(lines)


@mcp.tool()
def get_form_stats(form_id: str, since_date: str = None) -> str:
    """
    Estadísticas de uso de un formulario: total, usuarios, frecuencia.
    Para el formulario 991286 (Checklist Supervisión) incluye además:
    breakdown por supervisor, instalación, checklist items y puntajes.
    Incluye bloque JSON_DATA al final para uso programático.

    Args:
        form_id: ID del formulario
        since_date: Desde qué fecha (YYYY-MM-DD). Por defecto: últimos 30 días.
    """
    if not since_date:
        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    body = {
        "filters": [{"field": "answer_time", "operator": ">=", "type": "datetime", "val": since_date}],
        "order": [{"col": "answer_time", "type": "asc"}],
        "number_of_data": 500
    }
    records = _post(f"/forms/{form_id}/data/advanced", body).get("data", [])
    if not records:
        return f"No hay registros desde {since_date}."

    def _v(x):
        if x is None: return None
        if isinstance(x, str): return x
        if isinstance(x, bool): return "Sí" if x else "No"
        if isinstance(x, dict): return x.get("value")
        if isinstance(x, list) and x:
            f = x[0]
            return f.get("value") if isinstance(f, dict) else str(f)
        return str(x)

    def _sf(sub, key):
        if not sub: return None
        rows = sub if isinstance(sub, list) else [sub]
        if not rows: return None
        row = rows[0]
        if not isinstance(row, dict): return None
        cell = row.get(key)
        return cell.get("value") if isinstance(cell, dict) else cell

    dates: dict = {}
    supervisor_counts: dict = {}
    instalacion_counts: dict = {}
    libro_ok = libro_no = 0
    zona_ok = zona_no = 0
    caseta_issues_count: dict = {}
    puntajes = []
    records_data = []

    for r in records:
        day = str(r.get("answer_time", r.get("_create_time", "")))[:10]
        if day: dates[day] = dates.get(day, 0) + 1

        sup = _v(r.get("supervisor")) or "Sin asignar"
        supervisor_counts[sup] = supervisor_counts.get(sup, 0) + 1

        inst = _v(r.get("instalacion")) or "Desconocida"
        instalacion_counts[inst] = instalacion_counts.get(inst, 0) + 1

        libro = _v(r.get("libro_al_dia"))
        if libro == "Sí": libro_ok += 1
        elif libro == "No": libro_no += 1

        zona = _v(r.get("zona_de_trabajo_limpia"))
        if zona == "Sí": zona_ok += 1
        elif zona == "No": zona_no += 1

        caseta_raw = r.get("estado_de_la_caseta_garita_po")
        for item in ["puertas", "ventanas", "sillas", "escritorio_meson", "paredes"]:
            v = _sf(caseta_raw, item)
            if v and v != "Buen estado.":
                caseta_issues_count[item] = caseta_issues_count.get(item, 0) + 1

        pres_raw = r.get("uso_del_uniforme_y_presentaci")
        score_str = _sf(pres_raw, "resultado")
        score = int(score_str) if score_str and str(score_str).isdigit() else None
        guardia = _sf(pres_raw, "nombre_y_apellido")
        if score is not None: puntajes.append(score)

        caseta_raw2 = r.get("estado_de_la_caseta_garita_po")
        c_issues = []
        for item in ["puertas", "ventanas", "sillas", "escritorio_meson", "paredes"]:
            v2 = _sf(caseta_raw2, item)
            if v2 and v2 != "Buen estado.":
                c_issues.append(f"{item}: {v2}")

        records_data.append({
            "id": r.get("_id", r.get("id", "")),
            "fecha": _v(r.get("fecha")) or day,
            "hora": _v(r.get("hora")),
            "instalacion": inst,
            "zona": r.get("instalacion", {}).get("path", "") if isinstance(r.get("instalacion"), dict) else "",
            "supervisor": sup,
            "libro_al_dia": libro == "Sí" if libro else None,
            "zona_limpia": zona == "Sí" if zona else None,
            "caseta_ok": len(c_issues) == 0,
            "caseta_issues": c_issues,
            "puntaje_presentacion": score,
            "guardia": guardia,
            "answer_time": day,
        })

    avg_score = round(sum(puntajes) / len(puntajes), 1) if puntajes else None
    total = len(records)
    libro_pct = round(libro_ok / (libro_ok + libro_no) * 100, 1) if (libro_ok + libro_no) else None
    zona_pct = round(zona_ok / (zona_ok + zona_no) * 100, 1) if (zona_ok + zona_no) else None

    lines = [
        f"## Estadísticas formulario {form_id}",
        f"Período: desde {since_date}  |  Total: {total} registros\n",
        "### Por supervisor:"
    ]
    for sup, count in sorted(supervisor_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {sup}: {count}")
    lines.append("\n### Por instalación (top 10):")
    for inst, count in sorted(instalacion_counts.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"  {inst}: {count}")
    lines.append(f"\n### Checklist:")
    if libro_pct is not None: lines.append(f"  Libro al día: {libro_pct}% ({libro_ok}/{libro_ok+libro_no})")
    if zona_pct is not None: lines.append(f"  Zona limpia: {zona_pct}% ({zona_ok}/{zona_ok+zona_no})")
    if avg_score is not None: lines.append(f"  Puntaje presentación promedio: {avg_score}/100")
    if caseta_issues_count:
        lines.append("  Problemas caseta: " + ", ".join(f"{k}({v})" for k,v in caseta_issues_count.items()))
    lines.append("\n### Actividad por día:")
    for day in sorted(dates.keys()):
        lines.append(f"  {day}: {dates[day]} registro(s)")

    # Bloque JSON para uso programático (dashboard)
    json_data = {
        "total": total,
        "since": since_date,
        "supervisores": supervisor_counts,
        "instalaciones": instalacion_counts,
        "por_dia": dates,
        "checklist": {
            "libro_ok": libro_ok, "libro_no": libro_no, "libro_pct": libro_pct,
            "zona_ok": zona_ok, "zona_no": zona_no, "zona_pct": zona_pct,
            "puntaje_promedio": avg_score,
            "caseta_issues": caseta_issues_count,
        },
        "records": records_data,
    }
    lines.append("\n### JSON_DATA")
    lines.append(json.dumps(json_data, ensure_ascii=False))
    return "\n".join(lines)

# ── Utilidad ───────────────────────────────────────────────────────────────────

def _fmt(r: dict) -> str:
    rid = r.get("_id", "?")
    created = str(r.get("_create_time", ""))[:16]
    user = r.get("_user_name", r.get("_recipient_name", ""))
    parts = []
    for k, v in r.items():
        if not k.startswith("_") and v not in (None, "", [], {}) and len(parts) < 3:
            parts.append(f"{k}: {str(v)[:60]}")
    return f"[{rid}] {created} — {user}\n  {' | '.join(parts)}\n"


def _val(field):
    """Extrae el valor string de un campo Kizeo (flat o nested)."""
    if field is None:
        return None
    if isinstance(field, str):
        return field
    if isinstance(field, bool):
        return "Sí" if field else "No"
    if isinstance(field, dict):
        return field.get("value")
    if isinstance(field, list) and field:
        first = field[0]
        return first.get("value") if isinstance(first, dict) else str(first)
    return str(field)


def _subfield(subform, key):
    """Extrae un campo específico de un subformulario."""
    if not subform:
        return None
    rows = subform if isinstance(subform, list) else [subform]
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    cell = row.get(key)
    if isinstance(cell, dict):
        return cell.get("value")
    return cell


@mcp.tool()
def get_supervision_data(since_date: str = None) -> str:
    """
    Retorna JSON estructurado del Checklist de Supervisión para dashboard.
    Incluye: supervisor, instalación, zona, libro al día, zona limpia,
    estado caseta, puntaje de presentación del guardia.

    Args:
        since_date: Desde qué fecha (YYYY-MM-DD). Por defecto: últimos 30 días.
    """
    if not since_date:
        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    body = {
        "filters": [{"field": "answer_time", "operator": ">=", "type": "datetime", "val": since_date}],
        "order": [{"col": "answer_time", "type": "desc"}]
    }
    records = _post("/forms/991286/data/advanced", body).get("data", [])

    result = []
    for r in records:
        # Caseta
        caseta_raw = r.get("estado_de_la_caseta_garita_po")
        caseta_issues = []
        for item in ["puertas", "ventanas", "sillas", "escritorio_meson", "paredes"]:
            v = _subfield(caseta_raw, item)
            if v and v != "Buen estado.":
                caseta_issues.append(f"{item}: {v}")

        # Presentación
        pres_raw = r.get("uso_del_uniforme_y_presentaci")
        score_str = _subfield(pres_raw, "resultado")
        pres_score = int(score_str) if score_str and str(score_str).isdigit() else None
        guardia = _subfield(pres_raw, "nombre_y_apellido")

        # Instalación path (zona)
        inst_raw = r.get("instalacion")
        zona = inst_raw.get("path", "") if isinstance(inst_raw, dict) else ""

        libro = _val(r.get("libro_al_dia"))
        zona_limpia = _val(r.get("zona_de_trabajo_limpia"))

        result.append({
            "id": r.get("_id", r.get("id", "")),
            "fecha": _val(r.get("fecha")) or str(r.get("_create_time", ""))[:10],
            "hora": _val(r.get("hora")),
            "instalacion": _val(r.get("instalacion")),
            "zona": zona,
            "supervisor": _val(r.get("supervisor")),
            "libro_al_dia": libro == "Sí" if libro else None,
            "zona_limpia": zona_limpia == "Sí" if zona_limpia else None,
            "caseta_ok": len(caseta_issues) == 0,
            "caseta_issues": caseta_issues,
            "puntaje_presentacion": pres_score,
            "guardia": guardia,
            "create_time": str(r.get("_create_time", "")),
        })

    return json.dumps({"total": len(result), "since": since_date, "records": result}, ensure_ascii=False)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="sse")
