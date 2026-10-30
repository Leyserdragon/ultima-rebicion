"""Pantalla de registro de nuevas cuentas."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .security import MAX_USERNAME_LENGTH, PATRON_USERNAME, password_strength
from .user_manager import registrar_usuario

COLORES_FUERZA = ["#475569", "#ef4444", "#f59e0b", "#22c55e", "#10b981"]


class RegisterWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("CosmicStream Reader · Crear cuenta")
        self.resize(1340, 760)

        root = QWidget()
        self.setCentralWidget(root)

        principal = QVBoxLayout(root)
        principal.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tarjeta = QFrame()
        tarjeta.setObjectName("auth_card")
        tarjeta.setFixedWidth(440)

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(10)

        logo = QLabel(
            "<div align='center'>"
            "<span style='font-style: italic; font-weight: 900; font-size: 26px; color: #ff2a85;'>COSMIC</span>"
            "<span style='font-style: italic; font-weight: 900; font-size: 26px; color: #f8fafc;'>STREAM</span>"
            "</div>"
        )
        logo.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(logo)

        subtitulo = QLabel("Crea tu cuenta para acceder a la biblioteca")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitulo.setObjectName("muted")
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        etiqueta_usuario = QLabel("Nombre de usuario")
        etiqueta_usuario.setObjectName("form_label")
        layout.addWidget(etiqueta_usuario)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Solo letras y espacios (mín. 3)")
        self.txt_usuario.setFixedHeight(42)
        self.txt_usuario.setValidator(
            QRegularExpressionValidator(QRegularExpression(PATRON_USERNAME), self)
        )
        self.txt_usuario.setMaxLength(MAX_USERNAME_LENGTH)
        layout.addWidget(self.txt_usuario)

        etiqueta_pass = QLabel("Contraseña")
        etiqueta_pass.setObjectName("form_label")
        layout.addWidget(etiqueta_pass)

        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Mínimo 6 caracteres")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setFixedHeight(42)
        self.txt_password.textChanged.connect(self._actualizar_fuerza)
        layout.addWidget(self.txt_password)

        fila_fuerza = QHBoxLayout()
        fila_fuerza.setSpacing(4)
        self.barras = []
        for _ in range(4):
            barra = QFrame()
            barra.setFixedHeight(4)
            barra.setStyleSheet("background-color:#1f2431; border-radius:2px;")
            fila_fuerza.addWidget(barra)
            self.barras.append(barra)
        layout.addLayout(fila_fuerza)

        self.lbl_fuerza = QLabel("")
        self.lbl_fuerza.setObjectName("muted_small")
        layout.addWidget(self.lbl_fuerza)

        etiqueta_pass2 = QLabel("Confirmar contraseña")
        etiqueta_pass2.setObjectName("form_label")
        layout.addWidget(etiqueta_pass2)

        self.txt_password2 = QLineEdit()
        self.txt_password2.setPlaceholderText("Repite tu contraseña")
        self.txt_password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password2.setFixedHeight(42)
        self.txt_password2.returnPressed.connect(self.registrar)
        layout.addWidget(self.txt_password2)

        self.lbl_error = QLabel("")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setObjectName("error_label")
        self.lbl_error.setWordWrap(True)
        layout.addWidget(self.lbl_error)

        btn_crear = QPushButton("Crear cuenta")
        btn_crear.setObjectName("primary_btn")
        btn_crear.setFixedHeight(44)
        btn_crear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_crear.clicked.connect(self.registrar)
        layout.addWidget(btn_crear)

        btn_volver = QPushButton("← Volver al inicio de sesión")
        btn_volver.setObjectName("link_btn")
        btn_volver.setFixedHeight(36)
        btn_volver.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_volver.clicked.connect(self.controller.volver_al_login)
        layout.addWidget(btn_volver)

        principal.addWidget(tarjeta)
        self.txt_usuario.setFocus()

    def _actualizar_fuerza(self):
        nivel, etiqueta = password_strength(self.txt_password.text())
        for indice, barra in enumerate(self.barras):
            color = COLORES_FUERZA[nivel] if indice < nivel else "#1f2431"
            barra.setStyleSheet(f"background-color:{color}; border-radius:2px;")

        if not self.txt_password.text():
            self.lbl_fuerza.setText("")
        else:
            self.lbl_fuerza.setText(f"Seguridad: {etiqueta}")
            self.lbl_fuerza.setStyleSheet(f"color:{COLORES_FUERZA[nivel]}; font-size:11px;")

    def registrar(self):
        usuario = self.txt_usuario.text().strip()
        password = self.txt_password.text()  # sin strip: los espacios cuentan
        password2 = self.txt_password2.text()

        self.lbl_error.setText("")

        if not usuario or not password or not password2:
            self.lbl_error.setText("Completa todos los campos.")
            return

        if password != password2:
            self.lbl_error.setText("Las contraseñas no coinciden.")
            return

        ok, mensaje = registrar_usuario(usuario, password)
        if ok:
            QMessageBox.information(self, "Cuenta creada", mensaje)
            self.controller.volver_al_login()
        else:
            self.lbl_error.setText(mensaje)
