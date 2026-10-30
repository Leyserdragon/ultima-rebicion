"""Widget de calificación con estrellas (1 a 5).

Se usa en la ficha del libro: el usuario pulsa una estrella y el valor se
guarda en MySQL. El widget solo se encarga de la parte visual; quien lo usa
decide qué hacer cuando cambia la calificación escuchando la señal
``calificacionCambiada``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

COLOR_ACTIVA = "#fbbf24"
COLOR_INACTIVA = "#64748b"


class _Estrella(QPushButton):
    """Un botón con forma de estrella que avisa cuando el ratón pasa encima."""

    hover = Signal(int)

    def __init__(self, valor: int, parent=None):
        super().__init__("☆", parent)
        self.valor = valor
        self.setObjectName("star_btn")
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(30, 30)
        self.setToolTip(f"{valor} de 5")

    def enterEvent(self, event):
        self.hover.emit(self.valor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover.emit(0)
        super().leaveEvent(event)


class StarRatingWidget(QWidget):
    """Cinco estrellas pulsables.

    * ``valor()`` devuelve la calificación actual (0 = sin calificar).
    * ``set_valor(n)`` la cambia sin emitir la señal.
    * ``calificacionCambiada`` se emite cuando el usuario hace clic.
    """

    calificacionCambiada = Signal(int)

    def __init__(self, estrellas: int = 5, parent=None):
        super().__init__(parent)
        self._total = max(1, int(estrellas))
        self._valor = 0
        self._vista_previa = 0
        self.botones: list[_Estrella] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for valor in range(1, self._total + 1):
            boton = _Estrella(valor, self)
            boton.clicked.connect(lambda _=False, v=valor: self._al_hacer_clic(v))
            boton.hover.connect(self._al_pasar_raton)
            layout.addWidget(boton)
            self.botones.append(boton)

        self.setAccessibleName("Calificación en estrellas")
        self._pintar()

    # ------------------------------------------------------------- estado --
    def valor(self) -> int:
        return self._valor

    def set_valor(self, valor: int, emitir: bool = False):
        """Fija la calificación (0 para dejarla vacía)."""
        try:
            limpio = int(valor)
        except (TypeError, ValueError):
            limpio = 0
        self._valor = max(0, min(limpio, self._total))
        self._vista_previa = 0
        self._pintar()
        if emitir:
            self.calificacionCambiada.emit(self._valor)

    # -------------------------------------------------------------- eventos --
    def _al_hacer_clic(self, valor: int):
        self.set_valor(valor, emitir=True)

    def _al_pasar_raton(self, valor: int):
        if valor == self._vista_previa:
            return
        self._vista_previa = valor
        self._pintar()

    # ---------------------------------------------------------------- pintado --
    def _pintar(self):
        referencia = self._vista_previa or self._valor
        for boton in self.botones:
            activa = boton.valor <= referencia
            boton.setText("★" if activa else "☆")
            color = COLOR_ACTIVA if activa else COLOR_INACTIVA
            boton.setStyleSheet(
                "QPushButton#star_btn {"
                " background: transparent;"
                " border: none;"
                f" color: {color};"
                " font-size: 24px;"
                " padding: 0;"
                "}"
            )
