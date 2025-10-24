# app/blueprints/docs/routes.py
from __future__ import annotations
import os
from flask import current_app, render_template_string, send_from_directory, jsonify
from . import bp

# HTML mínimo para incrustar Scalar
_DOCS_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>API Docs</title>
    <style>html,body,#app{height:100%;margin:0}</style>
  </head>
  <body>
    <div id="app"></div>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
    <script>
      Scalar.createApiReference('#app', {
        url: '/openapi.json',           // tu spec
        theme: 'purple',                // 'default' | 'purple' | 'blue' | ...
        layout: 'modern',
        hideDownloadButton: false,
        servers: [{ url: window.location.origin }],
        metadata: {
          title: 'VGamers API',
          description: 'Docs interactivas para integradores y partners'
        }
      });
    </script>
  </body>
</html>
"""

@bp.get("/docs")
def scalar_docs():
    return render_template_string(_DOCS_HTML)

# Fallback: si no subes un archivo, servimos un SPEC mínimo inline
_INLINE_SPEC = {
  "openapi": "3.0.3",
  "info": { "title": "VGamers API", "version": "1.0.0",
            "description": "Endpoints públicos para integraciones B2B/B2C" },
  "servers": [{ "url": "http://localhost:5000" }],
  "paths": {
    "/health": { "get": { "summary": "Healthcheck",
      "responses": { "200": { "description": "OK" } } } },
    "/users": { "get": {
      "summary": "Listar usuarios",
      "tags": ["Usuarios"],
      "security": [{ "bearerAuth": [] }],
      "parameters": [
        { "name": "page", "in": "query", "schema": { "type": "integer", "minimum": 1 } }
      ],
      "responses": { "200": { "description": "Listado",
        "content": { "application/json": { "schema":
          { "type": "array", "items": { "$ref": "#/components/schemas/User" } } } } } }
    } }
  },
  "components": {
    "securitySchemes": {
      "bearerAuth": { "type": "http", "scheme": "bearer", "bearerFormat": "JWT" },
      "apiKey":     { "type": "apiKey", "in": "header", "name": "X-API-Key" }
    },
    "schemas": {
      "User": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"}, "email": {"type":"string","format":"email"}, "name":{"type":"string"}
        },
        "required": ["id","email"]
      }
    }
  }
}

@bp.get("/openapi.json")
def openapi_json():
    """
    1) Si existe app/blueprints/docs/static/openapi.json => lo sirve.
    2) Si no, responde el _INLINE_SPEC para no bloquear el /docs.
    """
    # Ubicación del static de ESTE blueprint
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    spec_path = os.path.join(static_dir, "openapi.json")
    if os.path.exists(spec_path):
        return send_from_directory(static_dir, "openapi.json", mimetype="application/json")
    return jsonify(_INLINE_SPEC)
