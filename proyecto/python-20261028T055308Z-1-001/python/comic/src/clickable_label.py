"""Etiqueta clicable usada por el lector para pasar de página."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel


class ClickablePageLabel(QLabel):
    leftClicked = Signal()
    rightClicked = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.leftClicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()
        else:
            super().mousePressEvent(event)

    def mostrar_mensaje(self, texto: str):
        """Limpia el pixmap y muestra un texto de error o aviso."""
        self.setPixmap(self.pixmap().__class__())
        self.setText(texto)
