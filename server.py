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
        filters.append({"col": "_create_time", "ope": ">=", "val": since_date})
    if user_name:
        filters.append({"col": "_user_name", "ope": "like", "val": f"%{user_name}%"})
    body = {
        "filters": filters,
        "order": {"col": "_update_time", "type": "desc"},
        "number_of_data": min(int(limit), 100)
    }
    records = _post(f"/forms/{form_id}/data/exports/json", body).get("data", [])
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
        "filters": [{"col": field, "ope": "like", "val": f"%{value}%"}],
        "order": {"col": "_update_time", "type": "desc"},
        "number_of_data": min(int(limit), 100)
    }
    records = _post(f"/forms/{form_id}/data/exports/json", body).get("data", [])
    if not records:
        return f"No se encontraron registros donde '{field}' contenga '{value}'."
    lines = [f"Búsqueda '{field}' ≈ '{value}' — {len(records)} resultado(s):\n"]
    for r in records:
        lines.append(_fmt(r))
    return "\n".join(lines)


@mcp.tool()
def get_form_stats(form_id: str, since_date: str = None) -> str:
    """
    Estadísticas de uso de un formulario: total de registros, usuarios activos, frecuencia.

    Args:
        form_id: ID del formulario
        since_date: Desde qué fecha (YYYY-MM-DD). Por defecto: últimos 30 días.
    """
    if not since_date:
        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    body = {
        "filters": [{"col": "_create_time", "ope": ">=", "val": since_date}],
        "order": {"col": "_create_time", "type": "asc"},
        "number_of_data": 500
    }
    records = _post(f"/forms/{form_id}/data/exports/json", body).get("data", [])
    if not records:
        return f"No hay registros desde {since_date}."
    user_counts: dict = {}
    dates: dict = {}
    for r in records:
        user = r.get("_user_name", r.get("_recipient_name", "Desconocido"))
        user_counts[user] = user_counts.get(user, 0) + 1
        day = str(r.get("_create_time", ""))[:10]
        if day:
            dates[day] = dates.get(day, 0) + 1
    lines = [
        f"## Estadísticas formulario {form_id}",
        f"Período: desde {since_date}  |  Total: {len(records)} registros\n",
        "### Por usuario:"
    ]
    for user, count in sorted(user_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {user}: {count}")
    lines.append("\n### Últimos 7 días con actividad:")
    for day in sorted(dates.keys())[-7:]:
        lines.append(f"  {day}: {dates[day]} registro(s)")
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

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")

