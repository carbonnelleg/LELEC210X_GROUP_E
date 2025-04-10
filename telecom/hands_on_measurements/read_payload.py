import sys
import os
import re
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QScrollArea, QFrame, QProgressBar,
    QMessageBox, QLabel
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg


class PayloadViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Payload Image Viewer - PyQt6")
        self.resize(1000, 800)

        self.layout = QVBoxLayout(self)

        self.open_button = QPushButton("Open TXT File")
        self.open_button.clicked.connect(self.load_file)
        self.layout.addWidget(self.open_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("No file loaded.")
        self.layout.addWidget(self.status_label)

    def load_file(self):
        self.clear_payloads()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(1)
        self.status_label.setText("Loading...")

        start_path = os.path.dirname(os.path.realpath(__file__)) + "/data/"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open TXT File", start_path, "Text Files (*.txt)")

        if not file_path:
            QMessageBox.information(self, "No File", "No file was selected.")
            self.status_label.setText("No file selected.")
            return

        with open(file_path, "r") as file:
            content = file.read()

        if not content.strip():
            QMessageBox.warning(self, "Empty File", "The selected file is empty.")
            self.status_label.setText("File is empty.")
            return

        # Find all payloads
        payloads = re.findall(r'payload=\[([0-9,\s]+?)\]', content)
        if not payloads:
            QMessageBox.information(self, "No Payloads", "No valid payloads found.")
            self.status_label.setText("No payloads found.")
            return

        valid_payloads = []
        for idx, payload_str in enumerate(payloads):
            try:
                values = [int(x.strip()) for x in payload_str.strip().split(',') if x.strip().isdigit()]
                if len(values) != 824:
                    continue

                # Packet header format:
                # - 1-byte version (0)
                # - 1-byte source address
                # - 2-byte (network byte order) payload length
                # - 4-byte message id (network byte order) monotonically increasing.
                # Packet format:
                # - Packet header
                # - Payload
                # - 16-byte tag

                payload_data = values[7:823-16]
                payload_np = np.array(payload_data, dtype=np.uint8)
                corrected_payload = (payload_np[1::2].astype(np.uint16) << 8) | payload_np[0::2].astype(np.uint16)

                # Extract image data
                image_data = corrected_payload[0:400]
                image_array = np.array(image_data, dtype=np.uint16).reshape((20, 20))
                valid_payloads.append(image_array)
            except Exception as e:
                print(f"Failed to parse payload {idx}: {e}")
                continue

        count = len(valid_payloads)
        if count == 0:
            QMessageBox.warning(self, "No Valid Images", "No valid 20x20 payloads found.")
            self.status_label.setText("No valid payloads.")
            return

        self.progress_bar.setMaximum(count)
        self.progress_bar.setValue(0)

        for idx, image_array in enumerate(valid_payloads):
            plot_widget = pg.PlotWidget()
            plot_widget.setAspectLocked(True)
            plot_widget.setInteractive(False)
            plot_widget.setFixedHeight(300)  # Force 300px height (as requested)

            img_item = pg.ImageItem(image_array)

            # Set colormap
            lut = pg.colormap.get('viridis').getLookupTable(0.0, 1.0, 256)
            img_item.setLookupTable(lut)

            # Disable downsampling (can cause blurry/blocky look)
            img_item.setAutoDownsample(False)

            # Add image to plot and lock view
            plot_widget.addItem(img_item)
            img_item.setLevels([0, np.max(image_array)])

            # Remove axes for cleaner look
            plot_widget.hideAxis('bottom')
            plot_widget.hideAxis('left')

            # Lock view to image size for pixel-perfect layout
            img_item.resetTransform()
            img_item.scale()
            plot_widget.setRange(xRange=(0, 20), yRange=(0, 20), padding=0)

            # Create a label showing the range (0 to max)
            range_text = f"Range: 0 - {np.max(image_array)}"
            text_item = pg.TextItem(text=range_text, color='w', anchor=(1, 1))
            # Set text position (e.g. top right corner of the image)
            plot_widget.addItem(text_item)

            # Add to layout
            frame = QFrame()
            frame_layout = QVBoxLayout(frame)
            frame_layout.addWidget(plot_widget)
            self.scroll_layout.addWidget(frame)

            self.progress_bar.setValue(idx + 1)
            QApplication.processEvents()


        self.status_label.setText(f"Displayed {count} payload(s).")

    def clear_payloads(self):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PayloadViewer()
    viewer.show()
    sys.exit(app.exec())
