"""Controlador principal: decide qué ventana se muestra y con qué datos.

Centralizar aquí la navegación evita el problema clásico de este proyecto:
al cerrar una ventana con la «X» la biblioteca quedaba oculta para siempre.

Nota técnica: no se usa ``WA_DeleteOnClose``. Esa opción destruye el objeto C++
de inmediato y deja la referencia de Python apuntando a memoria liberada
(``RuntimeError: Internal C++ object already deleted``). En su lugar, cada
ventana emite la señal ``closed`` y aquí se suelta la referencia para que el
recolector de basura libere la memoria de forma segura.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .admin_window import AdminWindow
from .auth import UsuarioSesion
from .book_detail_window import BookDetailWindow
from .library_window import LibraryWindow
from .login_window import LoginWindow
from .reader_window import ReaderWindow
from .register_window import RegisterWindow
from .styles import STYLE


class AppController:
    def __init__(self, app: QApplication):
        self.app = app
        self.app.setStyleSheet(STYLE)

        self.usuario: UsuarioSesion | None = None
        self._cerrando_sesion = False

        self.login: LoginWindow | None = None
        self.register_win: RegisterWindow | None = None
        self.library_window: LibraryWindow | None = None
        self.book_detail: BookDetailWindow | None = None
        self.admin: AdminWindow | None = None
        self.reader: ReaderWindow | None = None

    # ------------------------------------------------- compatibilidad --------- #
    @property
    def current_user(self) -> str | None:
        return self.usuario.username if self.usuario else None

    @property
    def current_user_id(self) -> int | None:
        return self.usuario.id_usuario if self.usuario else None

    @property
    def is_admin(self) -> bool:
        return bool(self.usuario and self.usuario.es_admin)

    # ------------------------------------------------------------ sesión ----- #
    def show_login(self):
        """Vuelve al login y cierra todo lo demás.

        La ventana nueva se muestra **antes** de cerrar las antiguas: si se
        cerrara primero la última ventana visible, Qt terminaría el programa
        (``quitOnLastWindowClosed``) antes de que apareciera el login.
        """
        self.usuario = None
        self.login = LoginWindow(self)
        self.login.show()
        self._cerrar_ventanas(excluir=self.login)
        self.login.raise_()
        self.login.activateWindow()

    def show_register(self):
        # Si ya hay una ventana de registro abierta se reutiliza: crear otra
        # dejaría la primera visible detrás, sin forma de cerrarla.
        if self.register_win is not None:
            self.register_win.show()
            self.register_win.raise_()
            self.register_win.activateWindow()
            return

        # El login se oculta (no se cierra) para poder volver sin recrearlo.
        if self.login is not None:
            self.login.hide()
        self.register_win = RegisterWindow(self)
        self.register_win.show()
        self.register_win.raise_()
        self.register_win.activateWindow()

    def volver_al_login(self):
        """Cierra el registro y vuelve al login ya existente."""
        if self.login is None:
            self.show_login()
        else:
            self.login.show()
            self.login.raise_()
            self.login.activateWindow()

        if self.register_win is not None:
            self.register_win.close()
            self.register_win = None

    def login_success(self, usuario: UsuarioSesion):
        self.usuario = usuario
        # 1.º se muestra la biblioteca, 2.º se cierran login y registro. Así
        # nunca quedan ventanas de acceso abiertas detrás de la aplicación.
        self.show_library()
        self._cerrar_ventanas(excluir=self.library_window)
        if self.library_window is not None:
            self.library_window.raise_()
            self.library_window.activateWindow()

    def cerrar_sesion(self):
        self.show_login()

    def _cerrar_ventanas(self, excluir=None):
        """Cierra las ventanas abiertas sin disparar la navegación.

        ``excluir`` permite conservar la ventana que se acaba de abrir.
        """
        self._cerrando_sesion = True
        try:
            for nombre in ("reader", "book_detail", "admin", "library_window",
                           "register_win", "login"):
                ventana = getattr(self, nombre, None)
                if ventana is not None and ventana is not excluir:
                    ventana.close()
        finally:
            self._cerrando_sesion = False

        for nombre in ("reader", "book_detail", "admin", "library_window",
                       "register_win", "login"):
            if getattr(self, nombre, None) is not excluir:
                setattr(self, nombre, None)

    # -------------------------------------------------------- biblioteca ----- #
    def show_library(self):
        if self._cerrando_sesion:
            return
        if self.library_window is None:
            self.library_window = LibraryWindow(self)
        else:
            self.library_window.refresh()
        self.library_window.show()
        self.library_window.raise_()
        self.library_window.activateWindow()

    def show_book_detail(self, libro: dict):
        # Un doble clic emite ``itemClicked`` y ``itemActivated``: sin esta
        # guarda se abrirían dos fichas y la primera quedaría huérfana.
        if self.book_detail is not None:
            self.book_detail.raise_()
            self.book_detail.activateWindow()
            return
        if self.library_window is not None:
            self.library_window.hide()
        self.book_detail = BookDetailWindow(self, libro)
        self.book_detail.closed.connect(self._detalle_cerrado)
        self.book_detail.show()

    def _detalle_cerrado(self):
        self.book_detail = None
        self.show_library()

    def show_admin(self):
        if self.admin is not None:
            self.admin.raise_()
            return
        if self.library_window is not None:
            self.library_window.hide()
        self.admin = AdminWindow(self, self.library_window)
        self.admin.closed.connect(self._admin_cerrado)
        self.admin.show()

    def _admin_cerrado(self):
        self.admin = None
        self.show_library()

    # ------------------------------------------------------------ lector ----- #
    def open_reader(self, libro: dict, pagina_inicial: int = 0):
        if self.reader is not None:
            self.reader.close()
        self.reader = ReaderWindow(
            self,
            libro["ruta_archivo"],
            id_libro=libro.get("id_libro"),
            titulo=libro.get("titulo", ""),
            pagina_inicial=pagina_inicial,
        )
        self.reader.closed.connect(self._lector_cerrado)
        self.reader.show()

    def _lector_cerrado(self):
        self.reader = None
        if self._cerrando_sesion:
            return
        # El progreso y las reseñas pudieron cambiar mientras se leía.
        if self.book_detail is not None:
            self.book_detail.actualizar()
        if self.library_window is not None:
            self.library_window.refresh()
