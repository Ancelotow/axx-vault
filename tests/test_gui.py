import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QImage, QPdfWriter, QPainter
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QLabel

from axxvault.gui import Job, MainWindow, PasswordDialog, Preview


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_selection_controls_and_deduplication(app, tmp_path):
    window = MainWindow()
    assert not window.read_button.isEnabled()
    one, two = tmp_path / "one.axx", tmp_path / "two.txt"
    one.touch()
    two.touch()
    window.add_files([one, one, two, tmp_path])
    assert window.table.rowCount() == 2
    assert not window.read_button.isEnabled()
    assert window.encrypt_button.isEnabled()
    window.table.clearSelection()
    window.table.selectRow(0)
    assert window.read_button.isEnabled()
    window.remove_selected()
    assert window.table.rowCount() == 1
    window.close()


def test_password_confirmation_and_clear(app):
    parent = MainWindow()
    dialog = PasswordDialog(True, parent)
    dialog.password.setText("short")
    dialog.validate(True)
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.password.setText("long-enough-password")
    dialog.confirm.setText("different-password")
    dialog.validate(True)
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.confirm.setText("long-enough-password")
    dialog.validate(True)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.take_password() == "long-enough-password"
    assert not dialog.password.text()
    assert not dialog.confirm.text()
    parent.close()


def test_text_preview_never_renders_html_and_clears_buffer(app):
    parent = MainWindow()
    preview = Preview("test.html", b'<script>alert("no")</script>', parent)
    editor = preview.findChild(QPlainTextEdit)
    assert editor.toPlainText() == '<script>alert("no")</script>'
    preview.accept()
    assert preview.buffer.data().isEmpty()
    parent.close()


def test_binary_not_treated_as_text(app):
    assert Preview.decode_text(b"\x00\x01executable") is None
    assert Preview.decode_text("été".encode("utf-16")) == "été"


def test_pdf_preview_loads_from_memory(app, tmp_path):
    from PySide6.QtPdf import QPdfDocument
    path = tmp_path / "document.pdf"
    writer = QPdfWriter(str(path))
    painter = QPainter(writer)
    painter.drawText(100, 100, "Document de test")
    painter.end()
    parent = MainWindow()
    preview = Preview("document.pdf", path.read_bytes(), parent)
    assert preview.document.status() == QPdfDocument.Status.Ready
    assert preview.document.pageCount() == 1
    preview.accept()
    assert preview.buffer.data().isEmpty()
    parent.close()


def test_job_finishes_and_clears_password(app, monkeypatch, tmp_path):
    import axxvault.gui as module

    class FakeEngine:
        def encrypt(self, *args):
            return tmp_path / "result.axx"

    monkeypatch.setattr(module, "Engine", FakeEngine)
    job = Job("encrypt", [Path("source")], tmp_path, "secret password")
    finished = []
    job.finished.connect(lambda *result: finished.append(result))
    job.run()
    assert finished == [(1, 0, False)]
    assert job.password == ""


@pytest.mark.integration
def test_complete_ui_encryption_with_real_worker(app, monkeypatch, tmp_path):
    import axxvault.gui as module
    source = tmp_path / "document.txt"
    source.write_text("Test du parcours complet", encoding="utf-8")
    output = tmp_path / "encrypted"
    output.mkdir()
    window = MainWindow()
    window.add_files([source])

    def accept_password(dialog):
        dialog.password.setText("a long enough password")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PasswordDialog, "exec", accept_password)
    monkeypatch.setattr(module.QFileDialog, "getExistingDirectory", lambda *args: str(output))
    window.start("encrypt")
    assert window.job is not None
    assert not window.encrypt_button.isEnabled()
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(15000)
    window.thread.finished.connect(loop.quit)
    loop.exec()
    if window.job is not None:
        window.cancel_job()
        window.thread.wait(5000)
        app.processEvents()
        pytest.fail("Le worker n’a pas terminé normalement.")
    assert (output / "document.txt.axx").is_file()
    assert window.table.item(0, 3).text() == "Terminé"
    assert window.encrypt_button.isEnabled()
    assert window.last_summary == (1, 0, False)
    window.close()
