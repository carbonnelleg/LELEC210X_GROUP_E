import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout,
    QHBoxLayout, QLabel, QSlider, QCheckBox, QTabWidget, QPlainTextEdit
)
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRect
import math
from matplotlib.cm import get_cmap

def getJetColor(value):
    """
    Map a normalized value [0,1] to a Jet-like QColor.
    This is an approximate implementation.
    """
    value = max(0.0, min(1.0, value))
    r = int(255 * min(max(4*value - 1.5, 0.0), 1.0))
    g = int(255 * min(max(4*abs(value-0.5) - 1.0, 0.0), 1.0))
    b = int(255 * min(max(1.5 - 4*value, 0.0), 1.0))
    return QColor(r, g, b)

def getViridisColor(value):
    cmap = get_cmap('viridis')
    rgba = cmap(value)
    r = int(255 * rgba[0])
    g = int(255 * rgba[1])
    b = int(255 * rgba[2])
    return QColor(r, g, b)

class Canvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas_width = 28
        self.canvas_height = 40
        self.scale = 10
        self.setFixedSize(self.canvas_width * self.scale, self.canvas_height * self.scale)
        self.grid = np.zeros((self.canvas_height, self.canvas_width), dtype=np.uint8)
        self.peaks = []  # Each peak: (col, row, weight)
        self.brush_width = 1  
        self.brush_intensity = 128
        self.show_first_deriv = False
        self.show_second_deriv = False

    def mousePressEvent(self, event):
        self.drawPixel(event)

    def mouseMoveEvent(self, event):
        self.drawPixel(event)

    def drawPixel(self, event):
        if event.buttons() & Qt.LeftButton:
            cx = event.x() // self.scale
            cy = event.y() // self.scale
            radius = self.brush_width / 2.0
            for j in range(int(cy - radius), int(cy + radius) + 1):
                for i in range(int(cx - radius), int(cx + radius) + 1):
                    if 0 <= i < self.canvas_width and 0 <= j < self.canvas_height:
                        dist = math.sqrt((cx - i) ** 2 + (cy - j) ** 2)
                        if dist <= radius:
                            weight = 1.0 - (dist / radius)
                            added = int(self.brush_intensity * weight)
                            self.grid[j, i] = min(255, int(self.grid[j, i]) + added)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        # Draw grid as an inverted grayscale image.
        for y in range(self.canvas_height):
            for x in range(self.canvas_width):
                val = self.grid[y, x]
                if val > 0:
                    display_val = 255 - val
                    rect = QRect(x * self.scale, y * self.scale, self.scale, self.scale)
                    painter.fillRect(rect, QColor(display_val, display_val, display_val))
        # Draw peaks (red circles)
        if self.peaks:
            pen = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen)
            for peak in self.peaks:
                cx = peak[0] * self.scale + self.scale // 2
                cy = peak[1] * self.scale + self.scale // 2
                peak_radius = self.scale * peak[2]
                painter.drawEllipse(cx - self.scale, cy - peak_radius, 2 * self.scale, 2 * peak_radius)
        # Overlay first derivative (4×4 squares in Jet colors)
        if self.show_first_deriv:
            factor_d = 0.5
            square_size = 4
            half_sq = square_size // 2
            for x in range(self.canvas_width):
                for y in range(1, self.canvas_height - 1):
                    d = (int(self.grid[y+1, x]) - int(self.grid[y-1, x])) / 2.0
                    cell_cx = int(x * self.scale + self.scale / 2)
                    cell_cy = int(y * self.scale + self.scale / 2)
                    offset = d * factor_d
                    norm = (d + 128) / 256.0
                    color = getJetColor(norm)
                    rect = QRect(cell_cx - half_sq, int(round(cell_cy - half_sq - offset)), square_size, square_size)
                    painter.fillRect(rect, color)
        # Overlay second derivative (4×4 squares in Jet colors)
        if self.show_second_deriv:
            factor_d2 = 0.2
            square_size = 4
            half_sq = square_size // 2
            for x in range(self.canvas_width):
                for y in range(1, self.canvas_height - 1):
                    d2 = (int(self.grid[y+1, x]) - 2 * int(self.grid[y, x]) + int(self.grid[y-1, x]))
                    cell_cx = int(x * self.scale + self.scale / 2)
                    cell_cy = int(y * self.scale + self.scale / 2)
                    offset = d2 * factor_d2
                    norm = (d2 + 128) / 256.0
                    color = getJetColor(norm)
                    rect = QRect(cell_cx - half_sq, int(round(cell_cy - half_sq - offset)), square_size, square_size)
                    painter.fillRect(rect, color)

    def compute_peaks(self):
        peaks = []
        for x in range(self.canvas_width):
            column = self.grid[:, x]
            rising = False
            start_rise = None
            for y in range(1, self.canvas_height):
                if column[y] > column[y - 1]:
                    if not rising:
                        rising = True
                        start_rise = y
                elif column[y] < column[y - 1] and rising:
                    center_y = int(round((start_rise + (y - 1)) / 2))
                    peaks.append((x, center_y, int(np.ceil((y - start_rise + 0.1) / 2))))
                    rising = False
            if rising:
                center_y = int(round((start_rise + (self.canvas_height - 1)) / 2))
                peaks.append((x, center_y, int(np.ceil((self.canvas_height - start_rise + 0.1) / 2))))
        self.peaks = peaks
        self.update()

    def clear_peaks(self):
        self.peaks = []
        self.update()

    def setBrushWidth(self, width):
        self.brush_width = width

    def setBrushIntensity(self, intensity):
        self.brush_intensity = intensity

    def setShowFirstDeriv(self, state):
        self.show_first_deriv = state
        self.update()

    def setShowSecondDeriv(self, state):
        self.show_second_deriv = state
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt Additive Radial Brush & Peak Finder")
        self.resize(1000, 600)  # Make the window a bit larger.
        # Create canvas and controls.
        self.canvas = Canvas(self)
        self.btnCompute = QPushButton("Compute Peaks", self)
        self.btnCompute.clicked.connect(self.computeAndUpdateData)
        self.btnClearPeaks = QPushButton("Clear Peaks", self)
        self.btnClearPeaks.clicked.connect(self.clearPeaksAndUpdateData)
        self.brushWidthSlider = QSlider(Qt.Horizontal)
        self.brushWidthSlider.setRange(1, 10)
        self.brushWidthSlider.setValue(1)
        self.brushWidthSlider.valueChanged.connect(self.canvas.setBrushWidth)
        bwLabel = QLabel("Brush Width")
        self.brushIntensitySlider = QSlider(Qt.Horizontal)
        self.brushIntensitySlider.setRange(0, 255)
        self.brushIntensitySlider.setValue(255)
        self.brushIntensitySlider.valueChanged.connect(self.canvas.setBrushIntensity)
        biLabel = QLabel("Brush Intensity")
        self.firstDerivCheck = QCheckBox("Show First Derivative")
        self.firstDerivCheck.toggled.connect(self.canvas.setShowFirstDeriv)
        self.secondDerivCheck = QCheckBox("Show Second Derivative")
        self.secondDerivCheck.toggled.connect(self.canvas.setShowSecondDeriv)
        
        # Create tab widget for data display.
        self.dataTabs = QTabWidget()
        self.peaksText = QPlainTextEdit()
        self.peaksText.setReadOnly(True)
        self.derivText = QPlainTextEdit()
        self.derivText.setReadOnly(True)
        self.compText = QPlainTextEdit()
        self.compText.setReadOnly(True)
        self.dataTabs.addTab(self.peaksText, "Peaks")
        self.dataTabs.addTab(self.derivText, "1st Deriv")
        self.dataTabs.addTab(self.compText, "Compression")
        
        # Arrange controls in layouts.
        sliderLayout = QHBoxLayout()
        sliderLayout.addWidget(bwLabel)
        sliderLayout.addWidget(self.brushWidthSlider)
        sliderLayout.addWidget(biLabel)
        sliderLayout.addWidget(self.brushIntensitySlider)
        checkboxLayout = QHBoxLayout()
        checkboxLayout.addWidget(self.firstDerivCheck)
        checkboxLayout.addWidget(self.secondDerivCheck)
        controlLayout = QVBoxLayout()
        controlLayout.addLayout(sliderLayout)
        controlLayout.addLayout(checkboxLayout)
        controlLayout.addWidget(self.btnCompute)
        controlLayout.addWidget(self.btnClearPeaks)
        
        leftLayout = QVBoxLayout()
        leftLayout.addWidget(self.canvas)
        leftLayout.addLayout(controlLayout)
        
        # Main horizontal layout: left is canvas+controls, right is data tabs.
        mainLayout = QHBoxLayout()
        mainLayout.addLayout(leftLayout)
        mainLayout.addWidget(self.dataTabs)
        container = QWidget()
        container.setLayout(mainLayout)
        self.setCentralWidget(container)
        self.updateDataTabs()
    
    def computeAndUpdateData(self):
        self.canvas.compute_peaks()
        self.updateDataTabs()
    
    def clearPeaksAndUpdateData(self):
        self.canvas.clear_peaks()
        self.updateDataTabs()
    
    def updateDataTabs(self):
        # Generate compressed peaks data.
        peaks_lines = ["Column | Peak Row | Weight"]
        for peak in self.canvas.peaks:
            peaks_lines.append(f"{peak[0]:2d}       | {peak[1]:2d}      | {peak[2]:2d}")
        peaks_lines.append("\nTotal Peaks: " + str(len(self.canvas.peaks)))
        self.peaksText.setPlainText("\n".join(peaks_lines))
        
        # Generate first derivative summary for each column.
        deriv_lines = ["Column | Max 1st Deriv | Row of Max"]
        nonzero_cols = 0
        for x in range(self.canvas.canvas_width):
            max_d = 0
            row_max = None
            for y in range(1, self.canvas.canvas_height - 1):
                d = (int(self.canvas.grid[y+1, x]) - int(self.canvas.grid[y-1, x])) / 2.0
                if abs(d) > abs(max_d):
                    max_d = d
                    row_max = y
            if row_max is not None:
                nonzero_cols += 1
                deriv_lines.append(f"{x:2d}       | {max_d:6.1f}      | {row_max:2d}")
            else:
                deriv_lines.append(f"{x:2d}       |    0.0      | --")
        deriv_lines.append("\nColumns with nonzero 1st Deriv: " + str(nonzero_cols))
        self.derivText.setPlainText("\n".join(deriv_lines))
        
        # Calculate compression efficiency.
        # Full grid: one byte per cell.
        full_bytes = self.canvas.canvas_width * self.canvas.canvas_height
        # Peaks encoding: 3 bytes per peak (only for columns that have peaks).
        peaks_bytes = len(self.canvas.peaks) * 3
        # 1st derivative encoding: 2 bytes per column with a nonzero deriv.
        first_deriv_bytes = nonzero_cols * 2
        comp_lines = [
            f"Full Grid Data: {full_bytes} bytes",
            f"Peaks Encoding: {peaks_bytes} bytes (actual count)",
            f"1st Deriv Encoding: {first_deriv_bytes} bytes (actual count)",
            f"Peaks Ratio: {100 * peaks_bytes / full_bytes:.1f}%",
            f"1st Deriv Ratio: {100 * first_deriv_bytes / full_bytes:.1f}%"
        ]
        self.compText.setPlainText("\n".join(comp_lines))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())