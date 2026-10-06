# Documentación de Núcleo IA

En esta carpeta y en la raíz del proyecto se encuentra la documentación oficial de **Núcleo IA**:

- `informacion/MANUAL_USUARIO.pdf`: Manual de usuario y arquitectura en formato PDF de alta calidad (diseñado tanto para principiantes como para desarrolladores de agentes).
- `MANUAL_HERMES_NUCLEO_IA.pdf`: Guía rápida paso a paso para la instalación de Hermes Agent conectado a Núcleo IA en una PC limpia.
- `MANUAL_OPENCODE_NUCLEO_IA.pdf`: Conexión y uso con OpenCode.
- `MANUAL_OPENWEBUI_NUCLEO_IA.pdf`: Conexión y uso con Open WebUI, tanto nativo como mediante Docker.
- `MANUAL_MODO_ORGANIZACION.pdf`: Guía completa del modo Profesional para instalaciones compartidas.

Los manuales se revisaron para esta versión de octubre de 2026 y los PDF se generan desde el manual completo de `docs para agentes/MANUAL_USUARIO_COMPLETO.md` con `python scripts/generar_manuales_actualizados.py`. El contenido editable y las guías de agentes están en `docs para agentes/`. Consulta también `docs para agentes/GUIA_AGENTES.md` para contratos de API y límites de cada capacidad. TTS: Edge TTS, SiliconFlow, Groq, Speechify y ElevenLabs; los dos últimos se seleccionan explícitamente, y ElevenLabs requiere `speech_generation` habilitado. La ruta de música solo simula metadatos.
