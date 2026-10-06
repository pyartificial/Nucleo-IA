"""Validacion rapida de la integracion multi-proveedor."""
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from proxy.proveedores.fabrica import crear_proveedor, tipos_disponibles
from proxy import rotador_cuentas

print("=" * 55)
print("  VALIDACION MULTI-PROVEEDOR")
print("=" * 55)

# 1. Tipos registrados
print(f"\n[OK] Tipos backend: {tipos_disponibles()}")

# 2. Cargar config
ruta = os.path.join(os.path.dirname(__file__), "..", "cuentas.json")
with open(ruta, "r") as f:
    config = json.load(f)

proveedores = config.get("proveedores", {})
for tipo, cfg in proveedores.items():
    cuentas = cfg.get("cuentas", [])
    print(f"\n[{tipo.upper()}] {len(cuentas)} cuentas:")
    for c in cuentas:
        prov = crear_proveedor(c, tipo)
        url = prov.construir_url()
        headers = prov.construir_headers()
        tiene_auth = "Authorization" in headers
        auth_str = "[AUTH]" if tiene_auth else "[SIN AUTH]"
        print(f"  {prov.identificar():30s} {auth_str} -> {url[:55]}")

# 3. Mapeo de modelos
mapeo = config.get("mapeo_modelos", {})
print(f"\n[MAPEO MODELOS] Ollama -> OpenRouter ({len(mapeo)} reglas):")
for ollama_m, or_m in mapeo.items():
    print(f"  {ollama_m:25s} -> {or_m}")

# 4. Rotador
rotador_cuentas.cargar_cuentas()
conteo = rotador_cuentas.contar_activas_por_tipo()
print(f"\n[ROTADOR] Cuentas activas:")
for tipo, info in conteo.items():
    print(f"  {tipo:12s} {info['activas']}/{info['total']}")

# 5. Test failover
print(f"\n[FAILOVER] Orden: {' -> '.join(rotador_cuentas.obtener_orden_failover())}")
print(f"[FAILOVER] Test rotacion (6 peticiones):")
for i in range(6):
    tipo, cuenta = rotador_cuentas.obtener_siguiente()
    if cuenta:
        modelo_trad = rotador_cuentas.traducir_modelo("kimi-k2.6:cloud", tipo)
        print(f"  #{i+1}: {cuenta['id']:16s} ({tipo:10s}) modelo={modelo_trad}")

print(f"\n{'=' * 55}")
print("  VALIDACION EXITOSA")
print(f"{'=' * 55}")
