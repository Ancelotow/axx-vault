"""Draw the application icon using Qt, without image generation services."""
from pathlib import Path
import struct

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication


def make_icons(folder: Path):
    folder.mkdir(exist_ok=True)
    image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    gradient = QLinearGradient(0, 0, 1024, 1024)
    gradient.setColorAt(0, QColor("#21394a"))
    gradient.setColorAt(1, QColor("#101720"))
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(40, 40, 944, 944), 220, 220)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#66dfb0"), 54, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawRoundedRect(QRectF(340, 240, 344, 370), 170, 170)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#66dfb0"))
    painter.drawRoundedRect(QRectF(247, 450, 530, 360), 70, 70)
    painter.setBrush(QColor("#152c31"))
    painter.drawEllipse(QRectF(469, 559, 86, 86))
    painter.drawRoundedRect(QRectF(489, 614, 46, 84), 18, 18)
    painter.end()
    image.save(str(folder / "icon.png"))
    icon_image = image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    png_path = folder / "icon-256.png"
    icon_image.save(str(png_path))
    png = png_path.read_bytes()
    (folder / "icon.ico").write_bytes(struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png)
    return image


if __name__ == "__main__":
    app = QApplication([])
    make_icons(Path(__file__).resolve().parent.parent / "assets")
