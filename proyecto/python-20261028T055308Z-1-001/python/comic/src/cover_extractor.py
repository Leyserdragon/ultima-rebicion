"""Extracción automática de portadas.

Antes, al subir un libro había que asignar la portada a mano. Ahora se toma la
primera página del PDF/CBZ/CBR, se reduce a un tamaño razonable y se guarda en
``data/covers/`` como JPEG.
"""

from __future__ import annotations

import io
import re
import secrets
import unicodedata
from pathlib import Path

try:  # pragma: no cover
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:  # pragma: no cover
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    try:
        import fitz
    except ImportError:
        fitz = None

from .library import BookSource

COVER_MAX_SIZE = (600, 900)
COVER_QUALITY = 85
COVER_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def slugify(texto: str) -> str:
    """Convierte un título en un nombre de archivo seguro."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto or "portada"


def _guardar_jpeg(datos: bytes, destino: Path) -> Path | None:
    """Reescala y guarda la imagen como JPEG. Devuelve la ruta o ``None``."""
    if Image is None:
        destino.write_bytes(datos)
        return destino
    try:
        with Image.open(io.BytesIO(datos)) as imagen:
            imagen = imagen.convert("RGB")
            imagen.thumbnail(COVER_MAX_SIZE, Image.LANCZOS)
            imagen.save(destino, "JPEG", quality=COVER_QUALITY, optimize=True)
        return destino
    except Exception as exc:  # pragma: no cover
        print(f"[!] No se pudo procesar la portada: {exc}")
        return None


def extraer_portada(archivo: str | Path, carpeta_destino: str | Path, titulo: str = "") -> Path | None:
    """Extrae la primera página de ``archivo`` como portada.

    Devuelve la ruta del JPEG generado o ``None`` si no se pudo.
    """
    archivo = Path(archivo)
    carpeta = Path(carpeta_destino)
    carpeta.mkdir(parents=True, exist_ok=True)

    if not archivo.exists():
        return None

    base = slugify(titulo or archivo.stem)
    destino = carpeta / f"{base}-{secrets.token_hex(3)}.jpg"

    try:
        if archivo.suffix.lower() in COVER_EXTS:
            return _guardar_jpeg(archivo.read_bytes(), destino)

        if archivo.suffix.lower() == ".pdf":
            if fitz is None:
                return None
            with fitz.open(archivo) as documento:
                if documento.page_count == 0:
                    return None
                pagina = documento.load_page(0)
                pixmap = pagina.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                return _guardar_jpeg(pixmap.tobytes("png"), destino)

        with BookSource(archivo) as libro:
            if libro.count() == 0:
                return None
            return _guardar_jpeg(libro.read_image(0, zoom=1.2), destino)

    except Exception as exc:  # pragma: no cover
        print(f"[!] No se pudo extraer la portada de «{archivo.name}»: {exc}")
        return None
