"""Actualiza el catálogo verificado de modelos de Cerebras."""
from ranking_openai_compatible import generar

if __name__ == "__main__":
    data = generar("cerebras")
    print(f"Cerebras: {data['total_modelos']} modelos descubiertos.")
