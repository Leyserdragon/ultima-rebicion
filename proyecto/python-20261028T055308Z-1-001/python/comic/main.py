"""Punto de entrada de CosmicStream Reader.

Ejecutar con::

    python main.py
"""

from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app import AppController
from src.db import PROJECT_ROOT

LOG_PATH = PROJECT_ROOT / "cosmicstream_error.log"


def _instalar_manejador_errores(app: QApplication) -> None:
    """Muestra un aviso legible y guarda el detalle si algo falla."""

    def manejar(tipo, valor, traza):
        if issubclass(tipo, KeyboardInterrupt):
            sys.__excepthook__(tipo, valor, traza)
            return
        detalle = "".join(traceback.format_exception(tipo, valor, traza))
        try:
            LOG_PATH.write_text(detalle, encoding="utf-8")
        except OSError:
            pass

        caja = QMessageBox()
        caja.setIcon(QMessageBox.Icon.Critical)
        caja.setWindowTitle("Error inesperado")
        caja.setText("Ocurrió un error inesperado en CosmicStream.")
        caja.setInformativeText(f"{valor}\n\nEl detalle se guardó en:\n{LOG_PATH}")
        caja.exec()

    sys.excepthook = manejar


def _icono() -> QIcon:
    ruta = PROJECT_ROOT / "data" / "icon.png"
    if ruta.exists():
        return QIcon(str(ruta))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    return QIcon(pixmap)


def main() -> int:
    (PROJECT_ROOT / "data" / "library").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "covers").mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("CosmicStream Reader")
    app.setApplicationDisplayName("CosmicStream Reader")
    app.setOrganizationName("CosmicStream")
    app.setWindowIcon(_icono())

    _instalar_manejador_errores(app)

    controlador = AppController(app)
    controlador.show_login()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
