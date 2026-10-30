"""Pantalla de inicio de sesión."""

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

from .auth import MENSAJE_CREDENCIALES, check_user
from .security import MAX_USERNAME_LENGTH, PATRON_USERNAME


class LoginWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("CosmicStream Reader · Iniciar sesión")
        self.resize(1340, 760)

        root = QWidget()
        self.setCentralWidget(root)

        principal = QVBoxLayout(root)
        principal.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tarjeta = QFrame()
        tarjeta.setObjectName("auth_card")
        tarjeta.setFixedWidth(440)

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(12)

        logo = QLabel(
            "<div align='center'>"
            "<span style='font-style: italic; font-weight: 900; font-size: 28px; color: #ff2a85;'>COSMIC</span>"
            "<span style='font-style: italic; font-weight: 900; font-size: 28px; color: #f8fafc;'>STREAM</span>"
            "</div>"
        )
        logo.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(logo)

        subtitulo = QLabel("Tu biblioteca de mangas, manhwas y cómics")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitulo.setObjectName("muted")
        layout.addWidget(subtitulo)
        layout.addSpacing(8)

        etiqueta_usuario = QLabel("Usuario")
        etiqueta_usuario.setObjectName("form_label")
        layout.addWidget(etiqueta_usuario)

        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Tu nombre de usuario")
        self.txt_usuario.setFixedHeight(44)
        # Solo letras y espacios: el validador descarta números y símbolos
        # mientras se escribe (y también al pegar texto).
        self.txt_usuario.setValidator(
            QRegularExpressionValidator(QRegularExpression(PATRON_USERNAME), self)
        )
        self.txt_usuario.setMaxLength(MAX_USERNAME_LENGTH)
        self.txt_usuario.returnPressed.connect(lambda: self.txt_password.setFocus())
        layout.addWidget(self.txt_usuario)

        etiqueta_password = QLabel("Contraseña")
        etiqueta_password.setObjectName("form_label")
        layout.addWidget(etiqueta_password)

        fila_password = QHBoxLayout()
        fila_password.setSpacing(6)
        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("••••••••••••")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setFixedHeight(44)
        self.txt_password.returnPressed.connect(self.iniciar_sesion)
        fila_password.addWidget(self.txt_password)

        self.btn_ojo = QPushButton("👁")
        self.btn_ojo.setCheckable(True)
        self.btn_ojo.setFixedSize(44, 44)
        self.btn_ojo.setToolTip("Mostrar u ocultar la contraseña")
        self.btn_ojo.toggled.connect(self._alternar_visibilidad)
        fila_password.addWidget(self.btn_ojo)
        layout.addLayout(fila_password)

        self.lbl_error = QLabel("")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setObjectName("error_label")
        self.lbl_error.setWordWrap(True)
        layout.addWidget(self.lbl_error)

        self.btn_login = QPushButton("Iniciar sesión")
        self.btn_login.setObjectName("primary_btn")
        self.btn_login.setFixedHeight(44)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self.iniciar_sesion)
        layout.addWidget(self.btn_login)

        separador = QLabel("— o —")
        separador.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separador.setObjectName("muted_small")
        layout.addWidget(separador)

        btn_registro = QPushButton("Crear cuenta nueva")
        btn_registro.setFixedHeight(42)
        btn_registro.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_registro.clicked.connect(self.ir_a_registro)
        layout.addWidget(btn_registro)

        principal.addWidget(tarjeta)
        self.txt_usuario.setFocus()

    def _alternar_visibilidad(self, visible: bool):
        self.txt_password.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    def iniciar_sesion(self):
        usuario = self.txt_usuario.text().strip()
        password = self.txt_password.text()  # sin strip: los espacios cuentan

        if not usuario or not password:
            self.lbl_error.setText("Completa usuario y contraseña.")
            return

        self.lbl_error.setText("")
        self.btn_login.setEnabled(False)
        self.btn_login.setText("Comprobando…")
        try:
            resultado = check_user(usuario, password)
        finally:
            self.btn_login.setEnabled(True)
            self.btn_login.setText("Iniciar sesión")

        if resultado.ok and resultado.usuario is not None:
            self.controller.login_success(resultado.usuario)
        else:
            self.lbl_error.setText("")
            self._avisar_fallo(resultado.mensaje)
            self.txt_password.selectAll()
            self.txt_password.setFocus()

    def _avisar_fallo(self, mensaje: str):
        """Muestra una ventana pequeña con el motivo del fallo de acceso."""
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        if mensaje == MENSAJE_CREDENCIALES:
            caja.setWindowTitle("Acceso denegado")
            caja.setText(MENSAJE_CREDENCIALES)
            caja.setInformativeText("Revisa el nombre de usuario y la contraseña.")
        else:
            # Bloqueo temporal, base de datos caída, campos vacíos…
            caja.setWindowTitle("No se pudo iniciar sesión")
            caja.setText(mensaje)
        caja.setStandardButtons(QMessageBox.StandardButton.Ok)
        caja.button(QMessageBox.StandardButton.Ok).setText("Entendido")
        caja.exec()

    def ir_a_registro(self):
        self.controller.show_register()
