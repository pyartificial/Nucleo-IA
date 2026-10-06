#!/usr/bin/env python3
"""Genera los manuales PDF públicos de Núcleo IA."""
from __future__ import annotations

from html import escape
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "informacion"
BLUE = colors.HexColor("#155AA8")
DARK = colors.HexColor("#18344F")
INK = colors.HexColor("#283D50")
PALE = colors.HexColor("#F1F6FB")
GREEN = colors.HexColor("#EAF7EF")
AMBER = colors.HexColor("#FFF5E6")
RED = colors.HexColor("#FDECEC")

regular = Path("/usr/share/fonts/liberation/LiberationSans-Regular.ttf")
bold = Path("/usr/share/fonts/liberation/LiberationSans-Bold.ttf")
mono = Path("/usr/share/fonts/liberation/LiberationMono-Regular.ttf")
if regular.exists() and bold.exists():
    pdfmetrics.registerFont(TTFont("Nucleo", str(regular)))
    pdfmetrics.registerFont(TTFont("Nucleo-Bold", str(bold)))
    BODY_FONT, BOLD_FONT = "Nucleo", "Nucleo-Bold"
else:
    BODY_FONT, BOLD_FONT = "Helvetica", "Helvetica-Bold"
if mono.exists():
    pdfmetrics.registerFont(TTFont("Nucleo-Mono", str(mono)))
    MONO_FONT = "Nucleo-Mono"
else:
    MONO_FONT = "Courier"


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName=BOLD_FONT,
                                fontSize=23, leading=28, textColor=DARK,
                                alignment=TA_CENTER, spaceAfter=8),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName=BODY_FONT,
                                   fontSize=10.5, leading=15, textColor=BLUE,
                                   alignment=TA_CENTER, spaceAfter=18),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=BOLD_FONT,
                             fontSize=15, leading=19, textColor=DARK,
                             spaceBefore=12, spaceAfter=6, keepWithNext=True),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=BOLD_FONT,
                             fontSize=11, leading=14, textColor=BLUE,
                             spaceBefore=8, spaceAfter=4, keepWithNext=True),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=BOLD_FONT,
                             fontSize=9.4, leading=12, textColor=INK,
                             spaceBefore=6, spaceAfter=3, keepWithNext=True),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=BODY_FONT,
                               fontSize=8.8, leading=12.7, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName=BODY_FONT,
                                fontSize=7.6, leading=10.2, textColor=INK),
        "small_header": ParagraphStyle("small_header", parent=base["BodyText"], fontName=BOLD_FONT,
                                        fontSize=7.6, leading=10.2, textColor=colors.white),
        "code": ParagraphStyle("code", parent=base["BodyText"], fontName=MONO_FONT,
                               fontSize=7.2, leading=10.2, textColor=DARK, spaceAfter=0),
    }


S = styles()


def p(text: str, style: str = "body") -> Paragraph:
    if style in {"h1", "h2"}:
        plain = re.sub(r"<[^>]+>", "", text).lower()
        anchor = re.sub(r"[^a-z0-9áéíóúüñ]+", "-", plain, flags=re.IGNORECASE).strip("-")
        text = f'<a name="{anchor}"/>{text}'
    return Paragraph(text, S[style])


def code(text: str) -> Table:
    safe = escape(text).replace("\n", "<br/>").replace(" ", "&nbsp;")
    table = Table([[p(safe, "code")]], colWidths=[17.0 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E9EFF5")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B8C8D8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def note(text: str, tone=PALE, border=BLUE) -> Table:
    table = Table([[p(text)]], colWidths=[17.0 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tone), ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def table(rows: list[list[str]], widths: list[float]) -> Table:
    cells = [[p(escape(value), "small_header" if row_index == 0 else "small") for value in row]
             for row_index, row in enumerate(rows)]
    result = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C8D8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return result


def numbered(items: list[str]) -> list[Paragraph]:
    return [p(f"<b>{index}.</b> {item}") for index, item in enumerate(items, 1)]


class Manual(BaseDocTemplate):
    def __init__(self, path: Path, short_title: str):
        self.short_title = short_title
        super().__init__(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                         topMargin=1.65 * cm, bottomMargin=1.55 * cm,
                         title=short_title, author="Núcleo IA")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self.footer))

    def footer(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#C7D4E1"))
        canvas.line(doc.leftMargin, 1.12 * cm, A4[0] - doc.rightMargin, 1.12 * cm)
        canvas.setFont(BODY_FONT, 6.8)
        canvas.setFillColor(colors.HexColor("#607487"))
        canvas.drawString(doc.leftMargin, 0.69 * cm, f"Núcleo IA · {self.short_title} · octubre de 2026")
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.69 * cm, f"Página {doc.page}")
        canvas.restoreState()


def cover(title: str, subtitle: str, purpose: str):
    return [
        Spacer(1, 1.2 * cm), p("NÚCLEO IA", "title"), p(title, "title"),
        p(subtitle, "subtitle"), note(f"<b>Objetivo.</b> {purpose}", GREEN, colors.HexColor("#3A9A63")),
        Spacer(1, 0.2 * cm),
    ]


def _manual_inline(text: str) -> str:
    """Convierte el marcado mínimo del manual a etiquetas de ReportLab."""
    value = escape(text)
    value = re.sub(r"`([^`]+)`", r"<font name='Nucleo-Mono'>\1</font>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="#155AA8">\1</link>', value)
    return value


def _manual_anchor(title: str) -> str:
    plain = re.sub(r"<[^>]+>", "", title).lower()
    return re.sub(r"[^a-z0-9áéíóúüñ]+", "-", plain, flags=re.IGNORECASE).strip("-")


def _manual_markdown_story(path: Path) -> tuple[list, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    story: list = []
    section_titles: list[str] = []
    index = 0
    skipped_title = False
    skip_markdown_index = False

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith(("# ", "## ")) and skip_markdown_index and stripped not in ("## Índice completo", "## Índice"):
            skip_markdown_index = False

        if stripped in ("## Índice completo", "## Índice"):
            skip_markdown_index = True
            index += 1
            continue
        if skip_markdown_index:
            index += 1
            continue

        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if not skipped_title:
                skipped_title = True
            else:
                section_titles.append(title)
                story.append(p(_manual_inline(title), "h1"))
            index += 1
            continue

        if stripped.startswith("## "):
            title = stripped[3:].strip()
            section_titles.append(title)
            story.append(p(_manual_inline(title), "h2"))
            index += 1
            continue

        if stripped.startswith("### "):
            title = stripped[4:].strip()
            story.append(p(_manual_inline(title), "h3"))
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            story.append(code("\n".join(block)))
            story.append(Spacer(1, 0.10 * cm))
            continue

        if stripped.startswith("> "):
            story.append(note(_manual_inline(stripped[2:].strip()), AMBER, colors.HexColor("#D58A16")))
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-+", lines[index + 1]):
            rows: list[list[str]] = []
            rows.append([cell.strip().replace("`", "") for cell in stripped.strip("|").split("|")])
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append([cell.strip().replace("`", "") for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            columns = max(len(row) for row in rows)
            for row in rows:
                row.extend([""] * (columns - len(row)))
            story.append(table(rows, [17.0 * cm / columns] * columns))
            story.append(Spacer(1, 0.10 * cm))
            continue

        if re.match(r"^[-*] ", stripped):
            while index < len(lines) and re.match(r"^\s*[-*] ", lines[index].strip()):
                item = re.sub(r"^\s*[-*] ", "", lines[index].strip())
                story.append(p(f"•&nbsp;&nbsp;{_manual_inline(item)}"))
                index += 1
            continue

        if re.match(r"^\d+\. ", stripped):
            while index < len(lines) and re.match(r"^\s*\d+\. ", lines[index].strip()):
                match = re.match(r"^\s*(\d+)\.\s+(.*)", lines[index])
                assert match is not None
                story.append(p(f"<b>{match.group(1)}.</b>&nbsp;&nbsp;{_manual_inline(match.group(2))}"))
                index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate or candidate.startswith(("# ", "## ", "### ", "```", "> ", "|")) or re.match(r"^[-*] |^\d+\. ", candidate):
                break
            paragraph.append(candidate)
            index += 1
        story.append(p(_manual_inline(" ".join(paragraph))))

    return story, section_titles


def _manual_toc(section_titles: list[str]) -> Table:
    cells = []
    for pos in range(0, len(section_titles), 2):
        row = []
        for title in section_titles[pos:pos + 2]:
            anchor = _manual_anchor(_manual_inline(title))
            row.append(p(f'<link href="#{anchor}" color="#155AA8">{_manual_inline(title)}</link>'))
        if len(row) == 1:
            row.append(p(""))
        cells.append(row)
    result = Table(cells, colWidths=[8.45 * cm, 8.45 * cm], hAlign="LEFT")
    result.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DCE5EE")),
    ]))
    return result


def build_user_complete():
    source = ROOT / "docs para agentes" / "MANUAL_USUARIO_COMPLETO.md"
    body, section_titles = _manual_markdown_story(source)
    story = cover(
        "Manual completo de usuario",
        "Guía pedagógica y autosuficiente para instalar, configurar y usar todas las capacidades",
        "Acompañar a una persona con poca experiencia técnica desde la instalación hasta el uso seguro, sin depender de otro documento.",
    )
    story += [p("Cómo usar este manual", "h1"),
              p("Podés leerlo en orden durante la primera instalación o usar el índice para ir directamente a una tarea. Los nombres que aparecen entre comillas corresponden a botones y opciones visibles. Los bloques con letra monoespaciada contienen direcciones, valores o instrucciones que deben copiarse sin cambiar."),
              p("Índice con enlaces", "h1"), _manual_toc(section_titles), Spacer(1, 0.2 * cm)]
    story += body
    Manual(OUT / "MANUAL_USUARIO.pdf", "Manual completo de usuario").build(story)


def build_hermes():
    story = cover("Hermes Agent + Núcleo IA", "Guía de conexión actualizada", "Usar Núcleo IA como endpoint personalizado de Hermes Agent.")
    story += [p("1. Requisitos", "h1"), p("Núcleo IA debe responder en /status. En Windows, Hermes se instala mediante Hermes Desktop. En Linux, macOS o WSL puede usarse el instalador oficial:"),
              code("curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"),
              p("2. Configuración", "h1")]
    story += numbered([
        "En una terminal ejecuta <b>hermes model</b>.",
        "Selecciona <b>Custom Endpoint</b>.",
        "Base URL: <b>http://127.0.0.1:8080/v1</b>.",
        "API key: <b>local</b> si Núcleo IA no exige autenticación; si AUTH_ENABLED=true, usa NUCLEO_API_KEY.",
        "Modelo: <b>tools</b> para agentes o <b>auto</b> para uso general.",
        "Selecciona una ventana de contexto de al menos 64K, según recomienda Hermes para endpoints personalizados.",
    ])
    story += [p("3. Verificación", "h1"), code('hermes chat\n# Pedir: "Responde exactamente HERMES_OK"'),
              p("Si falla, comprueba /healthz y /v1/models. Un 401 es una clave incorrecta; conexión rechazada indica que Núcleo IA no está iniciado; una espera larga puede ser failover."),
              note("Las herramientas pertenecen a Hermes; Núcleo IA selecciona el modelo y transporta las llamadas. Usa la ruta tools y mantén timeouts amplios.", AMBER, colors.HexColor("#D58A16")),
              p("4. Fuentes oficiales verificadas", "h1"),
              p("Hermes Agent: https://hermes-agent.nousresearch.com/docs/ y https://hermes-agent.nousresearch.com/docs/user-guide/cli-reference/")]
    Manual(OUT / "MANUAL_HERMES_NUCLEO_IA.pdf", "Hermes + Núcleo IA").build(story)


def build_opencode():
    story = cover("OpenCode + Núcleo IA", "Proveedor OpenAI-compatible", "Configurar OpenCode estable con las rutas lógicas de Núcleo IA.")
    story += [p("1. Conexión interactiva", "h1")]
    story += numbered([
        "Inicia Núcleo IA y comprueba http://127.0.0.1:8080/v1/models.",
        "En OpenCode ejecuta <b>/connect</b>, elige <b>Other</b> y usa el identificador <b>nucleo-ia</b>.",
        "Introduce <b>local</b> como clave, o NUCLEO_API_KEY si activaste autenticación.",
        "Guarda la configuración siguiente en opencode.json.",
    ])
    story += [code('''{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "nucleo-ia": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Núcleo IA",
      "options": {
        "baseURL": "http://127.0.0.1:8080/v1",
        "apiKey": "local"
      },
      "models": {
        "auto": { "name": "Núcleo IA Auto" },
        "tools": { "name": "Núcleo IA Tools" },
        "reasoning": { "name": "Núcleo IA Reasoning" }
      }
    }
  }
}'''),
              p("2. Elegir modelo", "h1"), p("Ejecuta <b>/models</b> y elige nucleo-ia/auto o nucleo-ia/tools. Si la configuración de tu versión se encuentra en otra ruta, usa <b>opencode debug paths</b> para localizarla."),
              p("3. Diagnóstico", "h1"),
              table([["Síntoma", "Revisión"], ["Proveedor no aparece", "JSON válido; clave singular provider; npm correcto"],
                     ["401", "apiKey y AUTH_ENABLED"], ["404", "baseURL debe terminar en /v1"],
                     ["Tools fallan", "Elegir tools y actualizar ranking"]], [6 * cm, 11 * cm]),
              p("4. Fuente oficial verificada", "h1"), p("OpenCode Providers: https://opencode.ai/docs/providers/ y Config: https://opencode.ai/docs/config/")]
    Manual(OUT / "MANUAL_OPENCODE_NUCLEO_IA.pdf", "OpenCode + Núcleo IA").build(story)


def build_openwebui():
    story = cover("Open WebUI + Núcleo IA", "Conexión OpenAI-compatible", "Añadir Núcleo IA como proveedor en una instalación nativa o Docker.")
    story += [p("1. Antes de conectar", "h1"), p("Inicia Núcleo IA y comprueba /healthz y /v1/models. Open WebUI es una interfaz separada; no reemplaza al proxy ni aporta cuentas de modelos."),
              p("2. Agregar la conexión", "h1")]
    story += numbered([
        "Abre Open WebUI y entra en <b>Settings → Admin → Connections</b>.",
        "En <b>Manage OpenAI API Connections</b>, pulsa <b>Add Connection</b>.",
        "Elige Standard/Compatible si aparecen pestañas.",
        "Escribe la URL adecuada de la tabla y una API key.",
        "Guarda y verifica. Los modelos auto, cheap, reasoning, tools y vision deben aparecer.",
    ])
    story += [table([["Dónde corre Open WebUI", "URL"], ["Aplicación nativa en la misma PC", "http://127.0.0.1:8080/v1"],
                     ["Docker Desktop", "http://host.docker.internal:8080/v1"],
                     ["Docker en Linux", "host.docker.internal con host-gateway, IP puente o red host"]], [7.5 * cm, 9.5 * cm]),
              note("Dentro de Docker, localhost apunta al propio contenedor. Por eso no debe usarse 127.0.0.1 para alcanzar un Núcleo IA que corre en el host.", AMBER, colors.HexColor("#D58A16")),
              PageBreak(), p("3. Clave y modelos", "h1"), p("Usa <b>local</b> si AUTH_ENABLED=false. Si está activa, usa NUCLEO_API_KEY. Si la detección automática no funciona, añade manualmente estos Model IDs: auto, cheap, reasoning, tools y vision."),
              p("4. Diagnóstico", "h1"),
              table([["Problema", "Solución"], ["Connection refused", "Iniciar Núcleo IA y revisar la URL desde el backend"],
                     ["Lista vacía", "Probar /v1/models y agregar Model IDs"], ["401", "Corregir API key"],
                     ["Docker no llega al host", "Agregar host.docker.internal:host-gateway o usar IP accesible"]], [6 * cm, 11 * cm]),
              p("5. Prueba final", "h1"),
              p("Selecciona <b>auto</b>, inicia un chat nuevo y pide una respuesta breve. Después prueba <b>tools</b> solo si tu flujo usa herramientas. Si un modelo lógico aparece pero falla, ejecuta el actualizador de rankings y revisa /status."),
              p("6. Seguridad de red", "h1"),
              p("Mantén Núcleo IA en 127.0.0.1 cuando todo corre en la misma PC. Si un contenedor necesita acceder por otra interfaz, limita el acceso con firewall y activa AUTH_ENABLED; no publiques el puerto 8080 directamente en Internet."),
              p("<b>Fuente oficial verificada:</b> docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/", "small")]
    Manual(OUT / "MANUAL_OPENWEBUI_NUCLEO_IA.pdf", "Open WebUI + Núcleo IA").build(story)


def build_organizacion():
    source = ROOT / "docs para agentes" / "MANUAL_MODO_ORGANIZACION.md"
    body, section_titles = _manual_markdown_story(source)
    story = cover(
        "Núcleo IA — Modo Profesional",
        "Uso compartido con permisos claros",
        "Guía completa para instalaciones con controles reforzados de acceso y administración.",
    )
    story += [p("Cómo usar este manual", "h1"),
              p("Leé el índice para ir a una tarea concreta o seguí los capítulos en orden durante la preparación. Cada procedimiento indica qué pantalla abrir, qué valor escribir y cómo comprobar el resultado."),
              p("Índice con enlaces", "h1"), _manual_toc(section_titles), Spacer(1, 0.2 * cm)]
    story += body
    Manual(OUT / "MANUAL_MODO_ORGANIZACION.pdf", "Núcleo IA — Modo Profesional").build(story)


def build_all():
    OUT.mkdir(parents=True, exist_ok=True)
    build_user_complete()
    build_hermes()
    build_opencode()
    build_openwebui()
    build_organizacion()
    for name in (
        "MANUAL_USUARIO.pdf", "MANUAL_HERMES_NUCLEO_IA.pdf",
        "MANUAL_OPENCODE_NUCLEO_IA.pdf", "MANUAL_OPENWEBUI_NUCLEO_IA.pdf",
        "MANUAL_MODO_ORGANIZACION.pdf",
    ):
        print(f"[OK] {OUT / name}")


if __name__ == "__main__":
    build_all()
