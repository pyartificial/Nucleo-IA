"""Actualiza el catálogo verificado de modelos de Mistral AI."""
from ranking_openai_compatible import generar

if __name__ == "__main__":
    data = generar("mistral")
    print(f"Mistral AI: {data['total_modelos']} modelos descubiertos.")
