"""Catálogo único de capacidades enrutable por Núcleo IA.

Las claves son contratos internos estables. Las etiquetas pueden cambiar sin
romper preferencias guardadas ni rutas del proxy.
"""
from __future__ import annotations


CAPACIDADES = {
    "vision_image": "Comprensión de imágenes",
    "vision_video": "Comprensión de video",
    "transcription_audio": "Transcripción de audio",
    "transcription_realtime": "Transcripción en tiempo real",
    "speech_generation": "Texto a voz",
    "speech_to_speech": "Voz a voz",
    "voice_cloning": "Clonación de voz",
    "voice_design": "Diseño y generación de voces",
    "audio_isolation": "Aislamiento de voz",
    "sound_effects": "Efectos de sonido",
    "dubbing": "Doblaje",
    "forced_alignment": "Alineación de audio y texto",
    "image_generation": "Imagen desde texto",
    "image_editing": "Edición de imágenes",
    "video_generation_text": "Video desde texto",
    "video_generation_image": "Video desde imagen",
    "video_editing": "Edición de video",
    "lip_sync": "Lip-sync y avatares",
    "embeddings": "Embeddings",
    "parse_documents": "Lectura de documentos",
    "reranking": "Reordenamiento de resultados",
    "music_generation": "Generación de música",
    "music_editing": "Edición e inpainting musical",
    "voice_agents": "Agentes de voz",
}

# Compatibilidad con configuraciones, rankings y clientes anteriores.
ALIASES_ANTIGUOS = {
    "vision": "vision_image",
    "transcripcion_audio": "transcription_audio",
    "tts": "speech_generation",
    "imagenes": "image_generation",
    "video": "video_generation_text",
    "parse_documentos": "parse_documents",
}

ALIAS_POR_CANONICA = {nuevo: viejo for viejo, nuevo in ALIASES_ANTIGUOS.items()}

FUENTES = {
    "vision_image": ("vision",),
    "vision_video": ("vision_video", "comprension_video"),
    "transcription_audio": ("transcripcion", "transcription_audio"),
    "transcription_realtime": ("transcripcion_tiempo_real", "transcription_realtime"),
    "speech_generation": ("tts", "speech_generation"),
    "speech_to_speech": ("voz_a_voz", "speech_to_speech"),
    "voice_cloning": ("clonacion_voz", "voice_cloning"),
    "voice_design": ("diseno_voz", "voice_design"),
    "audio_isolation": ("aislamiento_audio", "audio_isolation"),
    "sound_effects": ("efectos_sonido", "sound_effects"),
    "dubbing": ("doblaje", "dubbing"),
    "forced_alignment": ("alineacion_forzada", "forced_alignment"),
    "image_generation": ("imagen", "image_generation"),
    "image_editing": ("edicion_imagen", "image_editing"),
    "video_generation_text": ("video_texto", "video_generation_text", "video"),
    "video_generation_image": ("video_imagen", "video_generation_image"),
    "video_editing": ("edicion_video", "video_editing"),
    "lip_sync": ("lip_sync", "avatar"),
    "embeddings": ("embeddings",),
    "parse_documents": ("parse_documentos", "parse_documents"),
    "reranking": ("reranking",),
    "music_generation": ("musica", "music_generation"),
    "music_editing": ("edicion_musica", "music_editing"),
    "voice_agents": ("agentes_voz", "voice_agents"),
}


def canonica(clave: str) -> str:
    return ALIASES_ANTIGUOS.get(str(clave), str(clave))


def claves_compatibles(clave: str) -> tuple[str, ...]:
    clave = canonica(clave)
    antigua = ALIAS_POR_CANONICA.get(clave)
    return (clave, antigua) if antigua else (clave,)


def orden_guardado(ordenes: dict, clave: str) -> list:
    """Lee primero el alcance nuevo y cae al antiguo durante la migración."""
    for candidata in claves_compatibles(clave):
        value = ordenes.get("capacidad:" + candidata)
        if isinstance(value, list):
            return value
    return []
