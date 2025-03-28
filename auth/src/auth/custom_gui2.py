import sys
import time
import json
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QGridLayout, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, QUrl, QTimer, QSize
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QMutex, QMutexLocker
import pyqtgraph as pg
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import requests
import os

DEBUG_MODE_GUI = False
TARGET_FPS = 20

class AspectRatioWidget(QWidget):
    def __init__(self, widget, aspect_ratio, base_width, base_zoom, parent=None):
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
        desired_width = available_width
        desired_height = int(desired_width / self.aspect_ratio)
        if desired_height > available_height:
            desired_height = available_height
            desired_width = int(desired_height * self.aspect_ratio)
        self.widget.resize(desired_width, desired_height)
        new_zoom = self.base_zoom * (desired_width / self.base_width)
        self.widget.setZoomFactor(new_zoom)
        super().resizeEvent(event)


class CustomGUI(QMainWindow):
    mel_spec_num = 20
    mel_spec_len = 20
    current_class_names = ['chainsaw', 'fire', 'fireworks', 'gun']
    current_class_probas = np.array([0.25, 0.25, 0.25, 0.25])
    current_feature_vector = np.zeros((mel_spec_num, mel_spec_len))
    current_packet_data = b'0' * (12 + 800 + 16)
    current_choice = "chainsaw"
    lock = QMutex()
    last_update = time.time()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom GUI")
        self.resize(1200, 800)
        self.current_screen_size = self.size()
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.setCentralWidget(main_splitter)

        # Top panel: Bar plot and feature vector heatmap
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(top_splitter)
        self.bar_plot_widget = pg.PlotWidget()
        self.bar_plot_widget.setInteractive(False)
        self.bar_plot_widget.setYRange(0, 1)
        top_splitter.addWidget(self.bar_plot_widget)

        self.fv_plot_widget = pg.PlotWidget()
        self.fv_plot_widget.setInteractive(False)
        self.fv_img_item = pg.ImageItem()
        self.fv_plot_widget.addItem(self.fv_img_item)
        self.fv_plot_widget.invertY(True)
        top_splitter.addWidget(self.fv_plot_widget)

        # Bottom panel: Web view and metrics
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(bottom_splitter)
        self.webview = QWebEngineView()
        self.webview.setUrl(QUrl("http://lelec210x.sipr.ucl.ac.be/lelec210x/leaderboard"))
        self.webview.setZoomFactor(0.5)
        base_width = int(self.current_screen_size.width() * 0.8)
        base_height = int(self.current_screen_size.height() * 0.6)
        aspect_ratio = base_width / base_height
        webview_wrapper = AspectRatioWidget(self.webview, aspect_ratio, base_width, 0.5)
        bottom_splitter.addWidget(webview_wrapper)

        # Right panel: Metrics display
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
        self.packet_header_value = QLineEdit()
        self.packet_header_value.setReadOnly(True)
        self.packet_mac_label = QLabel("MAC:")
        self.packet_mac_value = QLineEdit()
        self.packet_mac_value.setReadOnly(True)
        self.metrics_grid_layout.addWidget(self.packet_header_label, 0, 0)
        self.metrics_grid_layout.addWidget(self.packet_header_value, 0, 1)
        self.metrics_grid_layout.addWidget(self.packet_mac_label, 1, 0)
        self.metrics_grid_layout.addWidget(self.packet_mac_value, 1, 1)

        self.metrics_selected_class_value = QLineEdit()
        self.metrics_selected_class_value.setReadOnly(True)
        self.metrics_max_proba_value = QLineEdit()
        self.metrics_max_proba_value.setReadOnly(True)
        self.metrics_packet_length_value = QLineEdit()
        self.metrics_packet_length_value.setReadOnly(True)
        self.metrics_feature_shape_value = QLineEdit()
        self.metrics_feature_shape_value.setReadOnly(True)
        self.metrics_grid_layout.addWidget(self.metrics_selected_class_value, 2, 1)
        self.metrics_grid_layout.addWidget(self.metrics_max_proba_value, 3, 1)
        self.metrics_grid_layout.addWidget(self.metrics_packet_length_value, 4, 1)
        self.metrics_grid_layout.addWidget(self.metrics_feature_shape_value, 5, 1)
        grid.addWidget(self.metrics_grid, 1, 0)

        self.timer = QTimer(self)
        self.timer.setInterval(int(1000 / TARGET_FPS))
        self.timer.timeout.connect(self.update_gui)
        self.timer.start()

        self.showMaximized()

    def update_gui(self):
        new_time = time.time()
        self.setWindowTitle(f"Custom GUI - FPS: {1 / (new_time - self.last_update):.2f}")
        self.last_update = new_time

        with QMutexLocker(self.lock):
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

            cmap = pg.colormap.get('viridis')
            colored_image = cmap.map(self.current_feature_vector.flatten(), mode='float')
            colored_image = colored_image.reshape(self.mel_spec_num, self.mel_spec_len, 4)
            self.fv_img_item.setImage(colored_image)

            self.packet_header_value.setText(self.current_packet_data[:12].hex())
            self.packet_mac_value.setText(self.current_packet_data[-16:].hex())
            self.metrics_selected_class_value.setText(self.current_choice)
            self.metrics_max_proba_value.setText(f"{np.max(self.current_class_probas)*100:.2f} %")
            self.metrics_packet_length_value.setText(str(len(self.current_packet_data)))
            self.metrics_feature_shape_value.setText(str(self.current_feature_vector.shape))

    def update_gui_params(self, current_class_names: list[str], current_class_probas: np.ndarray, current_feature_vector: np.ndarray, current_packet_data: bytes, current_choice: str):
        with QMutexLocker(self.lock):
            self.current_class_names = current_class_names
            self.current_class_probas = current_class_probas
            self.current_feature_vector = current_feature_vector
            self.current_packet_data = current_packet_data
            self.current_choice = current_choice

    def handle_request(self, data):
        """ Handle incoming JSON data to update the GUI. """
        params = json.loads(data)
        current_class_names = params["current_class_names"]
        current_class_probas = np.array(params["current_class_probas"])
        current_feature_vector = np.array(params["current_feature_vector"])
        current_packet_data = bytes.fromhex(params["current_packet_data"])
        current_choice = params["current_choice"]
        self.update_gui_params(current_class_names, current_class_probas, current_feature_vector, current_packet_data, current_choice)


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # Assume the data is a JSON object
        try:
            self.server.gui.handle_request(post_data)
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            self.send_response(400)
            self.end_headers()


class ThreadedHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, gui_instance):
        super().__init__(server_address, RequestHandlerClass)
        self.gui = gui_instance


def run_http_server(gui_instance):
    server_address = ('', 8000)
    httpd = ThreadedHTTPServer(server_address, SimpleHTTPRequestHandler, gui_instance)
    httpd.serve_forever()


def generate_gui_thread() -> tuple[CustomGUI, QApplication]:
    app = QApplication(sys.argv)
    window = CustomGUI()
    return window, app

def get_gui_status():
    # Sends a ping to the GUI to check if it is still running
    try:
        response = requests.get("http://localhost:8000")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    
def launch_gui_process():
    # Launch the GUI in a separate process using the same interpreter.
    import subprocess, sys, os
    root = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([sys.executable, os.path.join(root, "custom_gui2.py")], cwd=root)

if __name__ == '__main__':
    window, app = generate_gui_thread()

    # Start the HTTP server in a separate thread
    server_thread = threading.Thread(target=run_http_server, args=(window,))
    server_thread.daemon = True
    server_thread.start()

    sys.exit(app.exec())
