import sys
import math
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPainter, QImage, QColor, QMouseEvent

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QSlider, QTabWidget,
    QTextEdit, QCheckBox, QSizePolicy, QComboBox
)
import numpy as np

# --- Compression Algorithms ---

# No compression (identity)
def compress_none(data):
    return bytes(data)

# Modified Run-Length Encoding (with a marker in high bit)
def compress_rle(data):
    MIN_RUN_LENGTH = 1  # Set to 1 (or 2) to encode even short runs.
    compressed = bytearray()
    run_start = 0
    run_value = data[0]
    for i, value in enumerate(data[1:], 1):
        if value != run_value:
            run_length = i - run_start
            if run_length >= MIN_RUN_LENGTH:
                while run_length > 127:
                    compressed.append(0x80 | 127)
                    compressed.append(run_value)
                    run_length -= 127
                compressed.append(0x80 | run_length)
                compressed.append(run_value)
            else:
                # This branch will almost never be reached since MIN_RUN_LENGTH==1 means every run qualifies.
                for j in range(run_start, i):
                    compressed.append(data[j])
            run_start = i
            run_value = value
    run_length = len(data) - run_start
    if run_length >= MIN_RUN_LENGTH:
        while run_length > 127:
            compressed.append(0x80 | 127)
            compressed.append(run_value)
            run_length -= 127
        compressed.append(0x80 | run_length)
        compressed.append(run_value)
    else:
        for j in range(run_start, len(data)):
            compressed.append(data[j])
    return bytes(compressed)

# Delta Compression
def compress_delta(data):
    compressed = bytearray()
    prev = data[0]
    compressed.append(prev)
    for value in data[1:]:
        diff = (value - prev) & 0xff
        compressed.append(diff)
        prev = value
    return bytes(compressed)

# --- Decompression Algorithms ---

def decompress_none(data):
    # For no compression, just return the original data.
    return list(data)

def decompress_rle(data):
    # Uses our marker: if a byte has high bit set, it indicates a run.
    decompressed = []
    i = 0
    while i < len(data):
        b = data[i]
        if b & 0x80:
            run_length = b & 0x7F
            run_value = data[i+1]
            decompressed.extend([run_value] * run_length)
            i += 2
        else:
            decompressed.append(b)
            i += 1
    return decompressed

def decompress_delta(data):
    if not data:
        return []
    result = [data[0]]
    for diff in data[1:]:
        result.append((result[-1] + diff) & 0xff)
    return result

# Dictionary of compression implementations.
compression_algorithms = {
    "No Compression": compress_none,
    "RLE Compression": compress_rle,
    "Delta Compression": compress_delta,
}

# Dictionary of decompression implementations.
decompression_algorithms = {
    "No Compression": decompress_none,
    "RLE Compression": decompress_rle,
    "Delta Compression": decompress_delta,
}

# --- Canvas Widgets ---

class CanvasWidget(QWidget):
    def __init__(self, width=28, height=40, scale=10):
        super().__init__()
        self.canvas_width = width
        self.canvas_height = height
        self.scale = scale
        self.image = QImage(self.canvas_width, self.canvas_height, QImage.Format.Format_Grayscale8)
        self.image.fill(0)
        self.setFixedSize(self.canvas_width * self.scale, self.canvas_height * self.scale)
        self.brush_size = 3
        self.brush_intensity = 255
        self.drawing = False

    def setBrushSize(self, size):
        self.brush_size = size

    def setBrushIntensity(self, intensity):
        self.brush_intensity = intensity

    def clearCanvas(self):
        self.image.fill(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(self.rect(), self.image)
        if getattr(self, "showRLEOverlay", False):
            self.drawRLEOverlay()

    def drawBrush(self, pos):
        x = pos.x() // self.scale
        y = pos.y() // self.scale
        painter = QPainter(self.image)
        r = self.brush_size
        for i in range(-r, r+1):
            for j in range(-r, r+1):
                xi = x + i
                yj = y + j
                if 0 <= xi < self.canvas_width and 0 <= yj < self.canvas_height:
                    dist = math.sqrt(i**2 + j**2)
                    if dist <= r:
                        weight = max(0, 1 - (dist / (r+1)))
                        val = int(self.brush_intensity * weight)
                        current = QColor.fromRgb(self.image.pixel(xi, yj)).red()
                        new_val = max(current, val)
                        painter.setPen(QColor(new_val, new_val, new_val))
                        painter.drawPoint(xi, yj)
        painter.end()
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.drawing = True
            self.drawBrush(event.position().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing:
            self.drawBrush(event.position().toPoint())

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drawing = False

    def getCanvasData(self):
        data = []
        for j in range(self.canvas_height):
            for i in range(self.canvas_width):
                intensity = QColor.fromRgb(self.image.pixel(i, j)).red()
                data.append(intensity)
        return data

    def drawRLEOverlay(self):
        painter = QPainter(self)
        painter.setPen(QColor(255, 0, 0, 128))
        data = self.getCanvasData()
        if not data:
            return
        index = 0
        for j in range(self.canvas_height):
            run_start = 0
            run_value = data[index]
            for i in range(1, self.canvas_width):
                index += 1
                current = data[index]
                if current != run_value:
                    if i - run_start > 1:
                        x = run_start * self.scale
                        y = j * self.scale
                        width = (i - run_start) * self.scale
                        height = self.scale
                        painter.drawRect(x, y, width, height)
                    run_start = i
                    run_value = current
            index += 1
        painter.end()

# Read-only decompression canvas.
class DecompCanvasWidget(CanvasWidget):
    def __init__(self, width=28, height=40, scale=10):
        super().__init__(width, height, scale)
        # Disable drawing by not reacting to mouse events.
        self.setEnabled(False)

    def mousePressEvent(self, event: QMouseEvent):
        pass
    def mouseMoveEvent(self, event: QMouseEvent):
        pass
    def mouseReleaseEvent(self, event: QMouseEvent):
        pass

# --- Tabs for Compression Summaries ---

class CompressionTab(QWidget):
    def __init__(self, name, compress_func, canvas: CanvasWidget):
        super().__init__()
        self.compress_func = compress_func
        self.canvas = canvas
        self.name = name

        layout = QVBoxLayout()
        self.toggle = QCheckBox("Show operation")
        layout.addWidget(self.toggle)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.setLayout(layout)

    def updateContent(self):
        if self.toggle.isChecked():
            data = self.canvas.getCanvasData()
            compressed = self.compress_func(data)
            hex_str = compressed.hex()
            self.output.setPlainText(f"Compressed Data (hex):\n{hex_str}\nLength: {len(compressed)} bytes")
            if self.name == "RLE Compression":
                self.canvas.showRLEOverlay = True
        else:
            self.output.clear()
            if self.name == "RLE Compression":
                self.canvas.showRLEOverlay = False
        self.canvas.update()

class SummaryTab(QWidget):
    def __init__(self, canvas: CanvasWidget):
        super().__init__()
        self.canvas = canvas
        layout = QVBoxLayout()
        self.summaryText = QTextEdit()
        self.summaryText.setReadOnly(True)
        layout.addWidget(self.summaryText)
        self.setLayout(layout)

    def updateSummary(self):
        lines = []
        data = self.canvas.getCanvasData()
        for name, func in compression_algorithms.items():
            compressed = func(data)
            size = len(compressed)
            lines.append(f"{name}: {size} bytes")
        self.summaryText.setPlainText("\n".join(lines))

# --- Main Window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Make window larger.
        self.setWindowTitle("PyQT6 Compression App")
        self.resize(1200, 800)
        central = QWidget()
        main_layout = QHBoxLayout()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Left panel: Drawing canvas and controls.
        left_panel = QVBoxLayout()
        self.canvas = CanvasWidget()
        left_panel.addWidget(self.canvas)
        brushSizeLabel = QLabel("Brush Size")
        left_panel.addWidget(brushSizeLabel)
        self.brushSizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.brushSizeSlider.setMinimum(1)
        self.brushSizeSlider.setMaximum(10)
        self.brushSizeSlider.setValue(3)
        self.brushSizeSlider.valueChanged.connect(self.canvas.setBrushSize)
        left_panel.addWidget(self.brushSizeSlider)
        intensityLabel = QLabel("Brush Intensity")
        left_panel.addWidget(intensityLabel)
        self.intensitySlider = QSlider(Qt.Orientation.Horizontal)
        self.intensitySlider.setMinimum(0)
        self.intensitySlider.setMaximum(255)
        self.intensitySlider.setValue(255)
        self.intensitySlider.valueChanged.connect(self.canvas.setBrushIntensity)
        left_panel.addWidget(self.intensitySlider)
        clearButton = QPushButton("Clear Canvas")
        clearButton.clicked.connect(self.canvas.clearCanvas)
        left_panel.addWidget(clearButton)
        left_panel.addStretch()
        main_layout.addLayout(left_panel)

        # Middle panel: Tabs (Summary and Compression details).
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.summaryTab = SummaryTab(self.canvas)
        self.tabs.addTab(self.summaryTab, "Summary")
        self.compressionTabs = {}
        for name, func in compression_algorithms.items():
            tab = CompressionTab(name, func, self.canvas)
            self.compressionTabs[name] = tab
            self.tabs.addTab(tab, name)

        # Right panel: Decompression view and algorithm selector.
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Decompressed View"))
        # New: Let user choose which decompression algorithm to display.
        self.decompCombo = QComboBox()
        self.decompCombo.addItems(list(decompression_algorithms.keys()))
        right_panel.addWidget(QLabel("Select Decompression Algorithm:"))
        right_panel.addWidget(self.decompCombo)
        self.decompCanvas = DecompCanvasWidget()
        right_panel.addWidget(self.decompCanvas)
        right_panel.addStretch()
        main_layout.addLayout(right_panel)

        # Timer to refresh summary, compression tabs, and decompressed result.
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refreshTabs)
        self.timer.start()

    def refreshTabs(self):
        self.summaryTab.updateSummary()
        for tab in self.compressionTabs.values():
            tab.updateContent()
        # Determine the decompression algorithm selected by the user.
        selected_algo = self.decompCombo.currentText()
        decomp_func = decompression_algorithms[selected_algo]
        # For demonstration, use the corresponding compression algorithm.
        comp_func = compression_algorithms[selected_algo]
        data = self.canvas.getCanvasData()
        compressed = comp_func(data)
        decompressed_data = decomp_func(compressed)
        # Create a new QImage from the decompressed data.
        img = QImage(self.decompCanvas.canvas_width, self.decompCanvas.canvas_height, QImage.Format.Format_Grayscale8)
        idx = 0
        for j in range(self.decompCanvas.canvas_height):
            for i in range(self.decompCanvas.canvas_width):
                if idx < len(decompressed_data):
                    val = decompressed_data[idx]
                    # Set pixel from grayscale value.
                    img.setPixel(i, j, QColor(val, val, val).rgb())
                idx += 1
        self.decompCanvas.image = img
        self.decompCanvas.update()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()