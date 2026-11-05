from __future__ import annotations

from pathlib import Path
import sys
import threading

from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QIcon, QImageReader, QKeySequence, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import __version__
from .engine import Cancelled, Engine, VaultError, engine_path


STYLE = """
QWidget { background: #101720; color: #e9edf3; font-size: 13px; }
QMainWindow, QDialog { background: #101720; }
QLabel#eyebrow { color: #66dfb0; font-size: 12px; font-weight: 700; }
QLabel#title { font-size: 32px; font-weight: 700; }
QLabel#subtitle, QLabel#muted { color: #aab7c7; }
QFrame#panel { background: #17212e; border: 1px solid #2b3a4c; border-radius: 12px; }
QFrame#panel QLabel { background: transparent; }
QPushButton { background: #243347; border: 1px solid #3a4d64; border-radius: 7px;
              padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #30445d; border-color: #8ca2bd; }
QPushButton:pressed { background: #3b526c; }
QPushButton#primary { background: #66dfb0; color: #10271e; border-color: #66dfb0; }
QPushButton#primary:hover { background: #8ae9c3; }
QPushButton:disabled { color: #768293; background: #1b2635; border-color: #293646; }
QPushButton#primary:disabled { color: #768293; background: #1b2635; border-color: #293646; }
QLineEdit, QPlainTextEdit { background: #0e151e; border: 1px solid #44576e;
                         border-radius: 6px; padding: 10px; selection-background-color: #285e50; }
QLineEdit:focus { border-color: #66dfb0; }
QTableWidget { background: #121c28; alternate-background-color: #172230;
               border: 1px solid #2b3a4c; border-radius: 8px; gridline-color: #253448; }
QTableWidget::item { padding: 10px; }
QTableWidget::item:selected { background: #25483f; color: #f0fff9; }
QHeaderView::section { background: #1b2838; color: #aab7c7; border: 0;
                       padding: 12px; font-weight: 600; }
QProgressBar { border: 0; background: #253448; height: 6px; border-radius: 3px; }
QProgressBar::chunk { background: #66dfb0; border-radius: 3px; }
QToolTip { background: #243347; color: white; border: 1px solid #53667b; padding: 6px; }
QMenu { border: 1px solid #44576e; padding: 6px; }
QMenu::item:selected { background: #25483f; }
"""


def label(text: str, name: str = "") -> QLabel:
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setObjectName(name)
    result.setWordWrap(True)
    return result


def size_text(size: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024 or unit == "Go":
            return f"{size:.0f} {unit}" if unit == "o" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


class PasswordDialog(QDialog):
    def __init__(self, encrypt: bool, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Choisir un mot de passe" if encrypt else "Déverrouiller les fichiers")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(label("Protégez vos fichiers" if encrypt else "Votre mot de passe AxCrypt", "eyebrow"))
        layout.addWidget(label(
            "Utilisez une phrase de passe d’au moins 12 caractères. Conservez-la : elle est nécessaire pour relire vos fichiers."
            if encrypt else "Saisissez le mot de passe utilisé pour chiffrer ces fichiers. Aucun compte n’est nécessaire.", "muted"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mot de passe")
        self.password.setAccessibleName("Mot de passe")
        layout.addWidget(self.password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("Confirmer le mot de passe")
        self.confirm.setAccessibleName("Confirmer le mot de passe")
        if encrypt:
            layout.addWidget(self.confirm)
        show = QCheckBox("Afficher le mot de passe")
        show.toggled.connect(lambda visible: [field.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        ) for field in (self.password, self.confirm)])
        layout.addWidget(show)
        self.error = label("", "muted")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Chiffrer" if encrypt else "Déverrouiller")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(lambda: self.validate(encrypt))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self, encrypt: bool):
        password = self.password.text()
        if not password:
            self.error.setText("Saisissez un mot de passe.")
        elif encrypt and len(password) < 12:
            self.error.setText("Choisissez au moins 12 caractères.")
        elif encrypt and password != self.confirm.text():
            self.error.setText("Les deux mots de passe sont différents.")
        else:
            self.accept()

    def take_password(self) -> str:
        result = self.password.text()
        self.password.clear()
        self.confirm.clear()
        return result


class Preview(QDialog):
    def __init__(self, name: str, data: bytes, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle(f"Lecture — {name}")
        self.resize(960, 700)
        layout = QVBoxLayout(self)
        layout.addWidget(label(name, "eyebrow"))
        layout.addWidget(label("Lecture seule · Fermer cet aperçu retire le document de la vue.", "muted"))
        self.buffer = QBuffer(self)
        self.buffer.setData(QByteArray(data))
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.document = None
        if data.startswith(b"%PDF-"):
            self.document = QPdfDocument(self)
            self.document.load(self.buffer)
            view = QPdfView(self)
            view.setDocument(self.document)
            view.setPageMode(QPdfView.PageMode.MultiPage)
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            layout.addWidget(view, 1)
        else:
            reader = QImageReader(self.buffer)
            # SVG is intentionally not rendered: it can reference external resources.
            formats = {b"png", b"jpeg", b"jpg", b"bmp", b"webp", b"gif", b"tiff"}
            if bytes(reader.format()).lower() in formats:
                dimensions = reader.size()
                if dimensions.width() * dimensions.height() > 40_000_000:
                    layout.addWidget(label("Image trop grande pour l’aperçu. Déchiffrez-la pour la consulter."), 1)
                else:
                    image = reader.read()
                    area = QScrollArea()
                    image_label = QLabel()
                    image_label.setPixmap(QPixmap.fromImage(image))
                    image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    area.setWidget(image_label)
                    area.setWidgetResizable(True)
                    layout.addWidget(area, 1)
            else:
                text = self.decode_text(data)
                if text is None:
                    layout.addWidget(label("Ce format ne dispose pas d’un aperçu intégré.\n"
                                           "Utilisez « Déchiffrer » pour l’enregistrer et l’ouvrir avec votre logiciel habituel."), 1)
                else:
                    editor = QPlainTextEdit()
                    editor.setReadOnly(True)
                    editor.setPlainText(text)
                    layout.addWidget(editor, 1)
        close = QPushButton("Fermer l’aperçu")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    @staticmethod
    def decode_text(data: bytes) -> str | None:
        if len(data) > 4 * 1024 * 1024:
            return None
        try:
            text = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        except UnicodeError:
            return None
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            return None
        return text

    def done(self, result: int):
        if self.document:
            self.document.close()
        self.buffer.close()
        self.buffer.setData(QByteArray())
        super().done(result)


class Job(QObject):
    update = Signal(str, str, str)
    preview_ready = Signal(str, bytes)
    finished = Signal(int, int, bool)

    def __init__(self, operation: str, paths: list[Path], folder: Path | None, password: str):
        super().__init__()
        self.operation, self.paths, self.folder, self.password = operation, paths, folder, password
        self.cancel = threading.Event()

    @Slot()
    def run(self):
        succeeded = failed = 0
        try:
            engine = Engine()
            for path in self.paths:
                if self.cancel.is_set():
                    break
                self.update.emit(str(path), "En cours…", "")
                try:
                    if self.operation == "read":
                        name, data = engine.preview(path, self.password, self.cancel)
                        if self.cancel.is_set():
                            raise Cancelled("Opération annulée.")
                        self.preview_ready.emit(name, data)
                        detail = ""
                    else:
                        action = engine.encrypt if self.operation == "encrypt" else engine.decrypt
                        detail = str(action(path, self.folder, self.password, self.cancel))
                    succeeded += 1
                    self.update.emit(str(path), "Lu" if self.operation == "read" else "Terminé", detail)
                except Cancelled:
                    self.update.emit(str(path), "Annulé", "")
                    break
                except (VaultError, OSError) as error:
                    failed += 1
                    self.update.emit(str(path), "Échec", str(error))
                except Exception:
                    failed += 1
                    self.update.emit(str(path), "Échec", "Erreur inattendue pendant l’opération.")
        finally:
            self.password = ""
            self.finished.emit(succeeded, failed, self.cancel.is_set())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AxxVault — Fichiers AxCrypt")
        self.resize(1050, 740)
        self.setMinimumSize(780, 580)
        self.setAcceptDrops(True)
        self.job = None
        self.thread = None
        self.closing = False
        self.preview_data = None
        self.last_summary = (0, 0, False)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)
        top = QHBoxLayout()
        brand = label("AXXVAULT   /   FICHIERS PRIVÉS", "eyebrow")
        brand.setWordWrap(False)
        top.addWidget(brand)
        top.addStretch()
        top.addWidget(label("●  100 % local", "eyebrow"))
        layout.addLayout(top)
        layout.addWidget(label("Vos fichiers. Votre clé.", "title"))
        layout.addWidget(label("Lisez, déchiffrez et chiffrez vos fichiers AxCrypt, sans compte ni connexion.", "subtitle"))

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QHBoxLayout(panel)
        panel_layout.setContentsMargins(20, 18, 20, 18)
        intro = QVBoxLayout()
        intro.addWidget(label("Déposez vos fichiers ici"))
        intro.addWidget(label("Fichiers .axx pour la lecture · Tous types de fichiers pour le chiffrement", "muted"))
        panel_layout.addLayout(intro, 1)
        self.add_button = QPushButton("＋  Ajouter des fichiers")
        self.add_button.clicked.connect(self.choose_files)
        panel_layout.addWidget(self.add_button)
        layout.addWidget(panel)

        line = QHBoxLayout()
        self.count_label = label("Aucun fichier", "muted")
        self.count_label.setWordWrap(False)
        line.addWidget(self.count_label)
        line.addStretch()
        self.remove_button = QPushButton("Retirer la sélection")
        self.remove_button.clicked.connect(self.remove_selected)
        line.addWidget(self.remove_button)
        layout.addLayout(line)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Fichier", "Taille", "Type", "État"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self.refresh_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self.start("read"))
        layout.addWidget(self.table, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.read_button = QPushButton("Lire le fichier")
        self.decrypt_button = QPushButton("Déchiffrer…")
        self.encrypt_button = QPushButton("Chiffrer…")
        self.encrypt_button.setObjectName("primary")
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.hide()
        for button, operation in ((self.read_button, "read"), (self.decrypt_button, "decrypt"), (self.encrypt_button, "encrypt")):
            button.clicked.connect(lambda checked=False, op=operation: self.start(op))
            actions.addWidget(button)
        actions.addStretch()
        self.cancel_button.clicked.connect(self.cancel_job)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.status = label("Ajoutez des fichiers pour commencer. Les originaux sont conservés.", "muted")
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        layout.addWidget(label("Lecture AxCrypt 1 et 2 · Chiffrement AxCrypt 2 / AES-256 · Aucun écrasement de fichier", "muted"))
        self.setCentralWidget(root)

        file_menu = self.menuBar().addMenu("Fichier")
        add = QAction("Ajouter des fichiers…", self)
        add.setShortcut(QKeySequence.StandardKey.Open)
        add.triggered.connect(self.choose_files)
        file_menu.addAction(add)
        self.add_action = add
        quit_action = QAction("Quitter", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        help_menu = self.menuBar().addMenu("Aide")
        about = QAction("À propos", self)
        about.triggered.connect(self.about)
        help_menu.addAction(about)
        self.refresh_actions()
        if not engine_path().is_file():
            self.status.setText("Moteur manquant. Consultez le guide de compilation fourni avec l’application.")

    def about(self):
        QMessageBox.about(self, "À propos d’AxxVault", f"AxxVault {__version__}\n\n"
                          "Application indépendante compatible avec les fichiers AxCrypt.\n"
                          "Moteur : Xecrets Cli, issu d’AxCrypt (Svante Seleborg / Axantum / AxCrypt AB).\n"
                          "Logiciel libre, GPL version 3 ou ultérieure. Interface : Qt / PySide6.\n\n"
                          "Aperçu intégré : PDF, images et texte UTF-8 / UTF-16.\n"
                          "Les nouveaux fichiers nécessitent AxCrypt 2 ou un lecteur compatible.\n"
                          "AxxVault n’est pas affilié à AxCrypt AB.")

    def choose_files(self):
        if self.job:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers", "", "Tous les fichiers (*)")
        self.add_files(paths)

    def add_files(self, paths):
        if self.job:
            return
        existing = {self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(self.table.rowCount())}
        skipped = 0
        for value in paths:
            try:
                path = Path(value).resolve(strict=True)
                if not path.is_file():
                    skipped += 1
                    continue
                if str(path) in existing:
                    continue
                size = path.stat().st_size
            except OSError:
                skipped += 1
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, text in enumerate((path.name, size_text(size), "AxCrypt" if path.suffix.lower() == ".axx" else "Original", "Prêt")):
                item = QTableWidgetItem(text)
                item.setToolTip(str(path))
                self.table.setItem(row, col, item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, str(path))
            existing.add(str(path))
        self.table.selectAll()
        self.refresh_actions()
        self.status.setText("Sélectionnez un ou plusieurs fichiers, puis choisissez une action."
                            + (f" {skipped} dossier(s) ou fichier(s) inaccessible(s) ignoré(s)." if skipped else ""))

    def selected_paths(self) -> list[Path]:
        return [Path(self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole))
                for index in self.table.selectionModel().selectedRows()]

    def refresh_actions(self):
        paths = self.selected_paths()
        free = self.job is None
        self.count_label.setText(f"{self.table.rowCount()} fichier(s) · {len(paths)} sélectionné(s)")
        self.read_button.setEnabled(free and len(paths) == 1)
        self.decrypt_button.setEnabled(free and bool(paths))
        self.encrypt_button.setEnabled(free and bool(paths))
        self.remove_button.setEnabled(free and bool(paths))
        self.add_button.setEnabled(free)
        self.add_action.setEnabled(free)

    def remove_selected(self):
        if self.job:
            return
        for row in sorted((index.row() for index in self.table.selectionModel().selectedRows()), reverse=True):
            self.table.removeRow(row)
        self.refresh_actions()

    def dragEnterEvent(self, event):
        if not self.job and event.mimeData().hasUrls() and all(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def start(self, operation: str):
        paths = self.selected_paths()
        if self.job or not paths or (operation == "read" and len(paths) != 1):
            return
        if not engine_path().is_file():
            QMessageBox.warning(self, "Moteur manquant", "Consultez le guide de compilation pour installer le moteur Xecrets Cli.")
            return
        folder = None
        if operation != "read":
            chosen = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination")
            if not chosen:
                return
            folder = Path(chosen)
        dialog = PasswordDialog(operation == "encrypt", self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        password = dialog.take_password()
        dialog.deleteLater()
        if not accepted:
            return
        self.job = Job(operation, paths, folder, password)
        password = ""
        self.thread = QThread(self)
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.run)
        self.job.update.connect(self.update_row)
        self.job.preview_ready.connect(self.receive_preview)
        self.job.finished.connect(self.remember_summary)
        self.job.finished.connect(self.thread.quit)
        self.job.finished.connect(self.job.deleteLater)
        self.thread.finished.connect(self.job_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel_button.show()
        self.status.setText("Opération en cours…")
        self.refresh_actions()
        self.thread.start()

    @Slot(str, str, str)
    def update_row(self, source: str, state: str, detail: str):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == source:
                self.table.item(row, 3).setText(state)
                self.table.item(row, 3).setToolTip(detail or state)
                break
        if detail:
            self.status.setText(detail)

    @Slot(str, bytes)
    def receive_preview(self, name, data):
        self.preview_data = (name, data)

    @Slot(int, int, bool)
    def remember_summary(self, succeeded, failed, cancelled):
        self.last_summary = succeeded, failed, cancelled

    @Slot()
    def job_finished(self):
        self.job = self.thread = None
        self.progress.hide()
        self.cancel_button.hide()
        self.refresh_actions()
        succeeded, failed, cancelled = self.last_summary
        self.status.setText(f"{succeeded} réussi(s) · {failed} échec(s)" + (" · Annulé" if cancelled else "")
                            + (" — Survolez « Échec » pour voir la cause." if failed else " — Les originaux sont conservés."))
        if self.closing:
            self.preview_data = None
            self.close()
        elif self.preview_data:
            name, data = self.preview_data
            self.preview_data = None
            preview = Preview(name, data, self)
            data = b""
            preview.exec()
            preview.deleteLater()

    def cancel_job(self):
        if self.job:
            self.job.cancel.set()
            self.status.setText("Annulation en cours… Les fichiers déjà terminés sont conservés.")

    def closeEvent(self, event):
        if self.job:
            self.closing = True
            self.cancel_job()
            event.ignore()
        else:
            event.accept()


class Application(QApplication):
    file_open = Signal(str)

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            self.file_open.emit(event.file())
            return True
        return super().event(event)


def main():
    app = Application(sys.argv)
    app.setApplicationName("AxxVault")
    app.setOrganizationName("AxxVault")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    app.setWindowIcon(QIcon(str(root / "assets/icon.png")))
    QImageReader.setAllocationLimit(160)
    window = MainWindow()
    app.file_open.connect(lambda path: window.add_files([path]))
    window.add_files([arg for arg in sys.argv[1:] if not arg.startswith("-psn_")])
    window.show()
    sys.exit(app.exec())
