# Kizeo MCP Server

Servidor MCP remoto que conecta Claude directamente con Kizeo Forms.  
Una vez desplegado, cualquier miembro del equipo puede activarlo desde Claude sin configuración adicional.

---

## Deploy en Render.com (10 minutos, gratis)

### 1. Subir el código a GitHub

1. Crea un repositorio en [github.com/new](https://github.com/new)  
   - Nombre sugerido: `kizeo-mcp`  
   - Visibilidad: **Private** (recomendado)
2. Sube estos archivos al repositorio:
   - `server.py`
   - `requirements.txt`
   - `render.yaml`
   - `.gitignore`
   - `README.md`

### 2. Crear el servicio en Render

1. Ve a [render.com](https://render.com) e inicia sesión (puedes usar tu cuenta de GitHub)
2. Click en **New → Web Service**
3. Conecta tu repositorio `kizeo-mcp`
4. Render detecta el `render.yaml` automáticamente — confirma la configuración
5. En la sección **Environment Variables**, agrega:
   - Key: `KIZEO_TOKEN`
   - Value: `ckm_a8f02d1482f7b9fa77601b58da3b28aa3bb2fe27`
6. Click **Create Web Service**

Render construye y despliega el servidor. En ~2 minutos tendrás una URL del tipo:
```
https://kizeo-mcp.onrender.com
```

### 3. Registrar en Claude como conector

**Para cada miembro del equipo:**

1. Ve a [claude.ai/customize/connectors](https://claude.ai/customize/connectors)
2. Click en **Add connector**
3. Ingresa la URL del servidor:
   ```
   https://kizeo-mcp.onrender.com/mcp
   ```
4. Listo — Claude tendrá acceso a Kizeo en todas las conversaciones

---

## Herramientas disponibles

| Herramienta | Descripción |
|---|---|
| `list_forms` | Lista todos los formularios agrupados por categoría |
| `get_form_records` | Registros recientes de un formulario (filtros por fecha y usuario) |
| `get_record` | Detalle completo de un registro específico |
| `search_records` | Búsqueda en registros por cualquier campo |
| `get_form_stats` | Estadísticas de uso: totales, usuarios activos, frecuencia |

## Ejemplos de uso en Claude

```
Muéstrame las supervisiones de mayo
¿Cuántas inducciones hizo el equipo este mes?
Busca registros de EPP para Juan González
Dame las estadísticas del formulario de Checklist
```

---

## Notas de seguridad

- El token de Kizeo **nunca** queda en el repositorio (está en las variables de entorno de Render)
- Si el token se compromete, cámbialo en Render y en Kizeo sin tocar el código
- Render tier gratuito: el servidor duerme tras 15 min de inactividad y tarda ~30 segundos en despertar la primera llamada

## Actualizar el servidor

Cualquier push al repositorio dispara un redeploy automático en Render.

---

## Soporte

Repositorio mantenido por el equipo CKM Seguridad.
