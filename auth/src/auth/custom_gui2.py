import sys
import time
import asyncio
import base64
import json
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QGridLayout, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, QUrl, QTimer, QMutex, QMutexLocker
from PyQt6.QtWebEngineWidgets import QWebEngineView

import pyqtgraph as pg

from aiohttp import web
import qasync

DEBUG_MODE_GUI = False
TARGET_FPS = 20

class AspectRatioWidget(QWidget):
    def __init__(self, widget, aspect_ratio, base_width, base_zoom, parent=None):
        """
        widget: the child QWebEngineView
        aspect_ratio: desired width/height ratio
        base_width: reference width used to compute the zoom factor
        base_zoom: base zoom factor (e.g. 0.5)
        """
        super().__init__(parent)
        self.aspect_ratio = aspect_ratio
        self.widget = widget
        self.base_width = base_width
        self.base_zoom = base_zoom
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)

    def resizeEvent(self, event):
        available_width = event.size().width()
        available_height = event.size().height()

        # Compute desired dimensions while preserving the aspect ratio
        desired_width = available_width
        desired_height = int(desired_width / self.aspect_ratio)
        if desired_height > available_height:
            desired_height = available_height
            desired_width = int(desired_height * self.aspect_ratio)

        self.widget.resize(desired_width, desired_height)
        # Update zoom factor proportionally relative to the base width
        new_zoom = self.base_zoom * (desired_width / self.base_width)
        self.widget.setZoomFactor(new_zoom)
        super().resizeEvent(event)

class CustomGUI(QMainWindow):
    # Default parameters
    mel_spec_num = 20
    mel_spec_len = 20
    current_class_names = ['chainsaw', 'fire', 'fireworks', 'gun']
    current_class_probas = np.array([0.25, 0.25, 0.25, 0.25])
    current_feature_vector = np.zeros((mel_spec_num, mel_spec_len))
    # Dummy packet data: header (12 bytes), body (800 bytes), mac (16 bytes)
    current_packet_data = b'0' * (12 + 800 + 16)
    current_choice = "chainsaw"
    lock = QMutex()
    last_update = time.time()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom GUI")
        self.resize(1200, 800)
        self.current_screen_size = self.size()

        # Add packet counter for incoming updates
        self.packet_counter = 0
        self.last_packet_count_time = time.time()

        # Main vertical splitter divides top and bottom rows
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.setCentralWidget(main_splitter)

        #### Top Row: Two Panels (Left: Bar Plot, Right: Feature Vector using PyQtGraph)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(top_splitter)

        # Top-left: Bar Plot for Class Probabilities using PyQtGraph
        self.bar_plot_widget = pg.PlotWidget()
        self.bar_plot_widget.setInteractive(False)
        self.bar_plot_widget.setYRange(0, 1)
        top_splitter.addWidget(self.bar_plot_widget)

        # Top-right: Feature Vector Heatmap using PyQtGraph
        self.fv_plot_widget = pg.PlotWidget()
        self.fv_plot_widget.setInteractive(False)
        self.fv_img_item = pg.ImageItem()
        self.fv_plot_widget.addItem(self.fv_img_item)
        #self.fv_img_item.setLevels([0, 2**16]) # HACK : Check if the fv was not normalized before
        top_splitter.addWidget(self.fv_plot_widget)

        #### Bottom Row: Two Panels (Left: WebView, Right: Packet & Metrics)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(bottom_splitter)

        # Bottom-left: WebView with Aspect Ratio and dynamic zoom
        self.webview = QWebEngineView()
        self.webview.setUrl(QUrl("http://lelec210x.sipr.ucl.ac.be/lelec210x/leaderboard"))
        self.webview.setZoomFactor(0.5)  # base zoom factor

        base_width = int(self.current_screen_size.width() * 0.8)
        base_height = int(self.current_screen_size.height() * 0.6)
        aspect_ratio = base_width / base_height
        webview_wrapper = AspectRatioWidget(self.webview, aspect_ratio, base_width, 0.5)
        bottom_splitter.addWidget(webview_wrapper)

        # Bottom-right: Grid layout for packet data and metrics info
        bottom_widget = QWidget()
        grid = QGridLayout()
        bottom_widget.setLayout(grid)
        bottom_splitter.addWidget(bottom_widget)

        font_metrics = bottom_widget.font()
        font_metrics.setPointSize(12)

        self.metrics_grid = QWidget()
        self.metrics_grid_layout = QGridLayout()
        self.metrics_grid.setLayout(self.metrics_grid_layout)

        self.packet_header_label = QLabel("Header:")
        self.packet_header_label.setFont(font_metrics)
        self.packet_header_value = QLineEdit()
        self.packet_header_value.setReadOnly(True)
        self.packet_header_value.setFont(font_metrics)
        self.packet_mac_label = QLabel("MAC:")
        self.packet_mac_label.setFont(font_metrics)
        self.packet_mac_value = QLineEdit()
        self.packet_mac_value.setReadOnly(True)
        self.packet_mac_value.setFont(font_metrics)
        self.metrics_grid_layout.addWidget(self.packet_header_label, 0, 0)
        self.metrics_grid_layout.addWidget(self.packet_header_value, 0, 1)
        self.metrics_grid_layout.addWidget(self.packet_mac_label, 1, 0)
        self.metrics_grid_layout.addWidget(self.packet_mac_value, 1, 1)

        self.metric_selected_class = QLabel("Selected Class:")
        self.metric_selected_class.setFont(font_metrics)
        self.metric_max_proba = QLabel("Max Probability:")
        self.metric_max_proba.setFont(font_metrics)
        self.metric_packet_length = QLabel("Packet Length:")
        self.metric_packet_length.setFont(font_metrics)
        self.metric_feature_shape = QLabel("Feature Vector Shape:")
        self.metric_feature_shape.setFont(font_metrics)
        self.metrics_grid_layout.addWidget(self.metric_selected_class, 2, 0)
        self.metrics_grid_layout.addWidget(self.metric_max_proba, 3, 0)
        self.metrics_grid_layout.addWidget(self.metric_packet_length, 4, 0)
        self.metrics_grid_layout.addWidget(self.metric_feature_shape, 5, 0)

        self.metrics_selected_class_value = QLineEdit()
        self.metrics_selected_class_value.setReadOnly(True)
        self.metrics_selected_class_value.setFont(font_metrics)
        self.metrics_max_proba_value = QLineEdit()
        self.metrics_max_proba_value.setReadOnly(True)
        self.metrics_max_proba_value.setFont(font_metrics)
        self.metrics_packet_length_value = QLineEdit()
        self.metrics_packet_length_value.setReadOnly(True)
        self.metrics_packet_length_value.setFont(font_metrics)
        self.metrics_feature_shape_value = QLineEdit()
        self.metrics_feature_shape_value.setReadOnly(True)
        self.metrics_feature_shape_value.setFont(font_metrics)
        self.metrics_grid_layout.addWidget(self.metrics_selected_class_value, 2, 1)
        self.metrics_grid_layout.addWidget(self.metrics_max_proba_value, 3, 1)
        self.metrics_grid_layout.addWidget(self.metrics_packet_length_value, 4, 1)
        self.metrics_grid_layout.addWidget(self.metrics_feature_shape_value, 5, 1)
        grid.addWidget(self.metrics_grid, 1, 0)

        # Setup a timer to update displays at TARGET_FPS
        self.timer = QTimer(self)
        self.timer.setInterval(int(1000 / TARGET_FPS))
        self.timer.timeout.connect(self.update_gui)
        self.timer.start()

        self.showMaximized()

    def update_gui(self):
        new_time = time.time()
        # Calculate FPS based on GUI update timer
        fps = 1 / (new_time - self.last_update)
        self.last_update = new_time

        # Calculate PPS (packets per second) over the past interval (reset every second)
        current_time = time.time()
        interval = current_time - self.last_packet_count_time
        pps = self.packet_counter / interval if interval > 0 else 0
        if interval >= 1.0:
            self.packet_counter = 0
            self.last_packet_count_time = current_time

        # Update window title with both FPS and PPS
        self.setWindowTitle(f"Custom GUI - FPS: {fps:.2f} - Packets/s: {pps:.2f}")

        with QMutexLocker(self.lock):
            if DEBUG_MODE_GUI:
                # For testing: simulate random updates
                self.current_class_probas = np.random.rand(4)
                self.current_class_probas /= np.sum(self.current_class_probas)
                self.current_feature_vector = np.random.rand(self.mel_spec_num, self.mel_spec_len)

            # Update bar plot
            self.bar_plot_widget.clear()
            x = np.arange(len(self.current_class_names))
            width = 0.6
            bg_blue = pg.BarGraphItem(x=x, height=self.current_class_probas, width=width, brush='b')
            self.bar_plot_widget.addItem(bg_blue)
            highest_proba_idx = np.argmax(self.current_class_probas)
            bg_pink = pg.BarGraphItem(x=[highest_proba_idx], height=[self.current_class_probas[highest_proba_idx]], width=width, brush='m')
            self.bar_plot_widget.addItem(bg_pink)
            try:
                selected_class_idx = self.current_class_names.index(self.current_choice)
                bg_red = pg.BarGraphItem(x=[selected_class_idx], height=[self.current_class_probas[selected_class_idx]], width=width, brush='r')
                self.bar_plot_widget.addItem(bg_red)
            except ValueError:
                selected_class_idx = 0

            ax = self.bar_plot_widget.getAxis('bottom')
            ax.setTicks([list(zip(x, self.current_class_names))])
            self.bar_plot_widget.setYRange(0, 1)

            # Update feature vector heatmap
            cmap = pg.colormap.get('viridis')
            colored_image = cmap.map(self.current_feature_vector.flatten(), mode='float')
            colored_image = colored_image.reshape(self.mel_spec_num, self.mel_spec_len, 4)
            self.fv_img_item.setImage(colored_image)

            # Update metrics
            self.packet_header_value.setText(self.current_packet_data[:12].hex())
            self.packet_mac_value.setText(self.current_packet_data[-16:].hex())
            self.metrics_selected_class_value.setText(self.current_choice)
            self.metrics_max_proba_value.setText(f"{np.max(self.current_class_probas)*100:.2f} %")
            self.metrics_packet_length_value.setText(str(len(self.current_packet_data)))
            self.metrics_feature_shape_value.setText(str(self.current_feature_vector.shape))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()

    def update_gui_params(self,
                          current_class_names: list,
                          current_class_probas: np.ndarray,
                          current_feature_vector: np.ndarray,
                          current_packet_data: bytes,
                          current_choice: str,
                          mel_spec_len: int = 20,
                          mel_spec_num: int = 20):
        with QMutexLocker(self.lock):
            self.current_class_names = current_class_names
            self.current_class_probas = current_class_probas
            self.current_feature_vector = current_feature_vector
            self.current_packet_data = current_packet_data
            self.current_choice = current_choice
            self.mel_spec_len = mel_spec_len
            self.mel_spec_num = mel_spec_num
            # Increment the packet counter for each update received.
            self.packet_counter += 1

def generate_gui_thread() -> CustomGUI:
    window = CustomGUI()
    return window

#
# ASYNC SERVER CODE
#
async def handle_update(request):
    """
    Expects a JSON POST with keys:
      - current_class_names: list of strings
      - current_class_probas: list of numbers
      - current_feature_vector: nested list (2D)
      - current_packet_data: base64 encoded string (optional)
      - current_choice: string
      - mel_spec_len: int (optional)
      - mel_spec_num: int (optional)
    """
    try:
        data = await request.json()
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=400)

    # Use the existing values as defaults if keys are missing
    names = data.get("current_class_names", window.current_class_names)
    probas = np.array(data.get("current_class_probas", window.current_class_probas.tolist()))
    fv_list = data.get("current_feature_vector", window.current_feature_vector.tolist())
    fv = np.array(fv_list)
    packet_str = data.get("current_packet_data", None)
    if packet_str is not None:
        try:
            packet = base64.b64decode(packet_str)
        except Exception as e:
            return web.json_response({"status": "error", "message": "Invalid base64 for packet_data"}, status=400)
    else:
        packet = window.current_packet_data
    choice = data.get("current_choice", window.current_choice)
    mel_spec_len = data.get("mel_spec_len", window.mel_spec_len)
    mel_spec_num = data.get("mel_spec_num", window.mel_spec_num)

    # Thread-safe update of GUI parameters
    window.update_gui_params(names, probas, fv, packet, choice, mel_spec_len, mel_spec_num)
    return web.json_response({"status": "ok"})

async def start_server():
    app_server = web.Application()
    app_server.add_routes([web.post('/update', handle_update)])
    runner = web.AppRunner(app_server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8090)
    await site.start()
    print("Async server started at http://0.0.0.0:8090")
    # Keep the server running indefinitely.
    while True:
        await asyncio.sleep(3600)

#
# MAIN: Integrate the async server with Qt using qasync
#
if __name__ == '__main__':
    app = qasync.QApplication(sys.argv)
    window = generate_gui_thread()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    # Schedule the async server task using the loop
    loop.create_task(start_server())

    with loop:
        loop.run_forever()
