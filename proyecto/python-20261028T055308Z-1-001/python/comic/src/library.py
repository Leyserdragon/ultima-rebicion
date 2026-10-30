"""Acceso a los archivos de lectura: PDF, CBZ/ZIP, CBR/RAR y carpetas de imágenes.

Mejoras respecto a la versión anterior:

* El documento se abre **una sola vez** y se reutiliza (antes se abría y cerraba
  el PDF completo en cada cambio de página, lo que hacía el lector lento).
* Orden **natural** de páginas: ``pagina2.png`` va antes que ``pagina10.png``.
* Método :meth:`close` para liberar los descriptores de archivo al cerrar.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any

try:  # pragma: no cover
    import pymupdf as fitz  # PyMuPDF >= 1.24 (nombre nuevo del módulo)
except ImportError:  # pragma: no cover
    try:
        import fitz  # nombre antiguo, sigue funcionando
    except ImportError:
        fitz = None

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".avif"}
ARCHIVE_EXTENSIONS = {".cbz", ".zip", ".cbr", ".rar"}
ALLOWED_EXTENSIONS = {".pdf"} | ARCHIVE_EXTENSIONS | IMAGE_EXTENSIONS

FORMATO_POR_EXTENSION = {
    ".pdf": "PDF",
    ".cbz": "CBZ",
    ".zip": "ZIP",
    ".cbr": "CBR",
    ".rar": "RAR",
}


def orden_natural(texto: str) -> list[Any]:
    """Clave de ordenamiento que compara números como números.

    Sin esto, ``["pag10", "pag2"]`` se ordena como ``pag10, pag2``.
    """
    partes: list[Any] = []
    numero = ""
    for caracter in texto.lower():
        if caracter.isdigit():
            numero += caracter
        else:
            if numero:
                partes.append(int(numero))
                numero = ""
            partes.append(caracter)
    if numero:
        partes.append(int(numero))
    return partes


class Library:
    """Carpeta donde viven los archivos de la biblioteca."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def files(self) -> list[Path]:
        return sorted(
            (p for p in self.folder.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS),
            key=lambda p: orden_natural(p.name),
        )

    def add_file(self, source: str | Path) -> Path:
        """Copia un archivo a la biblioteca (sin sobrescribir originales)."""
        source = Path(source)
        if not source.exists() or not source.is_file():
            raise ValueError(f"No se puede copiar el archivo «{source}».")

        destino = self.folder / source.name
        if source.resolve() == destino.resolve():
            return destino

        # Si ya existe un archivo con ese nombre, se agrega un sufijo numérico
        # para no perder la versión anterior.
        contador = 1
        while destino.exists():
            destino = self.folder / f"{source.stem} ({contador}){source.suffix}"
            contador += 1

        shutil.copy2(source, destino)
        return destino

    def delete_file(self, path: str | Path) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError as exc:
            print(f"[!] No se pudo borrar «{path}»: {exc}")


class BookSource:
    """Lee páginas de un archivo como imágenes (bytes PNG/JPEG)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.kind = self._detect_kind()
        self._doc = None  # fitz.Document
        self._archive = None  # zipfile.ZipFile | rarfile.RarFile
        self._names: list[str] | None = None

    # -- detección y apertura ------------------------------------------------ #
    def _detect_kind(self) -> str:
        if not self.path.exists():
            return "unknown"
        if self.path.is_dir():
            return "folder"
        sufijo = self.path.suffix.lower()
        if sufijo == ".pdf":
            return "pdf"
        if sufijo in {".cbz", ".zip"}:
            return "zip"
        if sufijo in {".cbr", ".rar"}:
            return "rar"
        if sufijo in IMAGE_EXTENSIONS:
            return "image"
        return "unknown"

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def formato(self) -> str:
        if self.kind == "folder":
            return "CARPETA"
        if self.kind == "image":
            return "IMAGEN"
        return FORMATO_POR_EXTENSION.get(self.path.suffix.lower(), "DESCONOCIDO")

    def _documento(self):
        if self.kind != "pdf":
            return None
        if fitz is None:
            raise ValueError("PyMuPDF no está instalado; no se pueden abrir PDF.")
        if self._doc is None:
            self._doc = fitz.open(self.path)
        return self._doc

    def _archivo_comprimido(self):
        if self._archive is not None:
            return self._archive
        if self.kind == "zip":
            self._archive = zipfile.ZipFile(self.path)
        elif self.kind == "rar":
            try:
                import rarfile
            except ImportError as exc:
                raise ValueError("Falta el paquete rarfile para abrir CBR/RAR.") from exc
            self._archive = rarfile.RarFile(self.path)
        return self._archive

    # -- listado de páginas -------------------------------------------------- #
    def image_names(self) -> list[str]:
        if self._names is not None:
            return self._names

        if self.kind == "folder":
            self._names = sorted(
                (p.name for p in self.path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
                key=orden_natural,
            )
        elif self.kind in {"zip", "rar"}:
            archivo = self._archivo_comprimido()
            self._names = sorted(
                (
                    nombre
                    for nombre in archivo.namelist()
                    if not nombre.endswith("/") and Path(nombre).suffix.lower() in IMAGE_EXTENSIONS
                ),
                key=orden_natural,
            )
        elif self.kind == "image":
            self._names = [self.path.name]
        else:
            self._names = []
        return self._names

    def count(self) -> int:
        if self.kind == "pdf":
            try:
                return int(self._documento().page_count)
            except Exception as exc:  # pragma: no cover
                print(f"[!] No se pudo contar páginas de «{self.path.name}»: {exc}")
                return 0
        return len(self.image_names())

    # -- lectura ------------------------------------------------------------- #
    def read_image(self, index: int, zoom: float = 2.0) -> bytes:
        """Devuelve la página ``index`` como bytes de imagen."""
        if index < 0:
            raise IndexError("El índice de página no puede ser negativo.")

        if self.kind == "pdf":
            documento = self._documento()
            if index >= documento.page_count:
                raise IndexError(f"La página {index + 1} no existe (total: {documento.page_count}).")
            pagina = documento.load_page(index)
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return pixmap.tobytes("png")

        paginas = self.image_names()
        if not 0 <= index < len(paginas):
            raise IndexError(f"La página {index + 1} no existe (total: {len(paginas)}).")

        if self.kind == "image":
            return self.path.read_bytes()
        if self.kind == "folder":
            return (self.path / paginas[index]).read_bytes()
        return self._archivo_comprimido().read(paginas[index])

    # -- limpieza ------------------------------------------------------------ #
    def close(self) -> None:
        """Libera el archivo abierto."""
        for recurso in (self._doc, self._archive):
            try:
                if recurso is not None:
                    recurso.close()
            except Exception:  # pragma: no cover
                pass
        self._doc = None
        self._archive = None
        self._names = None

    def __enter__(self) -> "BookSource":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __del__(self):  # pragma: no cover
        self.close()
