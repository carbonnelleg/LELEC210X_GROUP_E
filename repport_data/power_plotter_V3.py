import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
from tkinter import filedialog, Tk, messagebox
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QLineEdit, QFileDialog
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import matplotlib.style as mplstyle
import plotly.graph_objects as go  # New import for Plotly

close_all = False

# ======================
# Helper Functions
# ======================
def get_script_root():
    try:
        return Path(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        return Path(os.path.dirname(os.path.abspath(sys.argv[0])))

def parse_value(value_str):
    """
    Parse a string with a unit and return the numeric value in base SI units.
    E.g. "0.250000mV" returns 0.250000e-3, "200.00000uS" returns 200e-6.
    """
    value_str = value_str.strip().lower()
    for unit in ['mv', 'v', 'us', 's']:
        if unit in value_str:
            try:
                num = float(value_str.replace(unit, '').replace('?', ''))
            except Exception:
                num = 0.0
            if unit == 'mv':
                return num * 1e-3
            elif unit == 'v':
                return num
            elif unit == 'us':
                return num * 1e-6
            elif unit == 's':
                return num
    try:
        return float(value_str)
    except:
        return 0.0

# ======================
# Preferences
# ======================
def load_or_create_preferences(folder: Path):
    pref_path = folder / "plotter_preferences.npz"
    if pref_path.exists():
        prefs = np.load(pref_path, allow_pickle=True)
        return dict(prefs)
    else:
        return {
            'CH1_V_PER_DIV': 0.2,         # volts per division for CH1 (user defined)
            'CH2_V_PER_DIV': 1.0,         # volts per division for CH2 (user defined)
            'CH1_OFFSET_DIVS': -3.0,      # offset in divisions for CH1
            'CH2_OFFSET_DIVS': 0.0,       # offset in divisions for CH2
            'R': 100.54,                # shunt resistor (Ohm)
            # Power formula as a Python expression. Variables available:
            # CH1, CH2, OFFSET_CH1, OFFSET_CH2, R
            'power_formula': "((CH2 - OFFSET_CH2) - (CH1 - OFFSET_CH1)) * (CH1 - OFFSET_CH1) / R"
        }

def save_preferences(folder: Path, preferences: dict):
    np.savez(folder / "plotter_preferences.npz", **preferences)

# ======================
# Preference Editor GUI
# ======================
class PreferenceEditor(QWidget):
    def __init__(self, initial_folder: Path, initial_prefs: dict):
        super().__init__()
        self.setWindowTitle("Configure Preferences")
        self.selected_folder = initial_folder
        self.preferences = initial_prefs
        self.setMinimumWidth(600)  # Wider window for long paths
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Folder selector button with initial directory
        self.folder_btn = QPushButton(f"Select Folder\nCurrent: {self.selected_folder}")
        self.folder_btn.setMinimumWidth(600)
        self.folder_btn.clicked.connect(self.choose_folder)
        layout.addWidget(self.folder_btn)

        # Create editable fields for each preference
        self.fields = {}
        def add_field(label_text, key):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            row.addWidget(lbl)
            field = QLineEdit(str(self.preferences[key]))
            field.setMinimumWidth(400)
            row.addWidget(field)
            layout.addLayout(row)
            self.fields[key] = field

        add_field("CH1 Volts/Div", 'CH1_V_PER_DIV')
        add_field("CH2 Volts/Div", 'CH2_V_PER_DIV')
        add_field("CH1 Offset (divs)", 'CH1_OFFSET_DIVS')
        add_field("CH2 Offset (divs)", 'CH2_OFFSET_DIVS')
        add_field("Shunt Resistor (Ohm)", 'R')
        add_field("Power Formula", 'power_formula')

        btn = QPushButton("Confirm and Continue")
        btn.clicked.connect(self.finish)
        layout.addWidget(btn)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Data Folder", str(self.selected_folder))
        if folder:
            self.selected_folder = Path(folder)
            self.preferences = load_or_create_preferences(self.selected_folder)
            self.folder_btn.setText(f"Select Folder\nCurrent: {self.selected_folder}")
            for key, field in self.fields.items():
                field.setText(str(self.preferences.get(key, "")))

    def finish(self):
        for key, field in self.fields.items():
            text = field.text().strip()
            if key == 'power_formula':
                self.preferences[key] = text
            else:
                try:
                    self.preferences[key] = float(text)
                except ValueError:
                    messagebox.showwarning("Invalid Input", f"Invalid numeric value for {key}")
                    return
        save_preferences(self.selected_folder, self.preferences)
        self.close()

# ======================
# CSV Processor
# ======================
class CSVProcessor:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.metadata = {}
        self.time = None
        self.voltage_data = {}
        self.ch1_v_per_adc = None
        self.ch2_v_per_adc = None
        self.ch1_probe_att = None
        self.ch2_probe_att = None
        self.time_interval = None
        self._process_file()

    def _process_file(self):
        with open(self.file_path, 'r') as f:
            header_lines = [f.readline().strip() for _ in range(7)]
        for line in header_lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                key = parts[0].replace(":", "").strip().lower()
                self.metadata[key] = parts[1:]
        if "voltage per adc value" in self.metadata:
            try:
                self.ch1_v_per_adc = parse_value(self.metadata["voltage per adc value"][0])
                self.ch2_v_per_adc = parse_value(self.metadata["voltage per adc value"][1])
            except Exception as e:
                raise ValueError("Failed to parse voltage per ADC value") from e
        else:
            raise ValueError("Voltage per ADC value not found in CSV header.")
        if "probe attenuation" in self.metadata:
            try:
                self.ch1_probe_att = float(self.metadata["probe attenuation"][0].replace('X', ''))
                self.ch2_probe_att = float(self.metadata["probe attenuation"][1].replace('X', ''))
            except Exception as e:
                self.ch1_probe_att = self.ch2_probe_att = 1.0
        else:
            self.ch1_probe_att = self.ch2_probe_att = 1.0
        if "time interval" in self.metadata:
            try:
                self.time_interval = parse_value(self.metadata["time interval"][0])
            except Exception as e:
                raise ValueError("Failed to parse time interval") from e
        else:
            raise ValueError("Time interval not found in CSV header.")
        df = pd.read_csv(self.file_path, skiprows=8)
        num_samples = len(df)
        self.time = np.arange(num_samples) * self.time_interval
        self.voltage_data['CH1'] = df.iloc[:, 1].values * self.ch1_probe_att * 1e-3  # Convert to volts
        self.voltage_data['CH2'] = df.iloc[:, 2].values * self.ch2_probe_att * 1e-3  # Convert to volts

# ======================
# Plot Window
# ======================
class PlotWindow(QMainWindow):
    def __init__(self, file_info, processor, power_mW, folder_path, energy_mJ):
        super().__init__()
        self.setWindowTitle(f"Power Analysis - {file_info['filename']}")
        self.file_info = file_info
        self.processor = processor
        self.power = power_mW  # Power in mW
        self.folder_path = folder_path
        self.total_energy = energy_mJ  # Energy in mJ
        self.centered_time = self.processor.time - self.processor.time[0]
        mplstyle.use('fast')
        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        self.fig = Figure(figsize=(8, 6))
        self.canvas = FigureCanvasQTAgg(self.fig)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        self.ax = self.fig.add_subplot(111)
        self.line, = self.ax.plot(self.centered_time, self.power)
        self.energy_text = self.ax.text(
            0.98, 0.95,
            f"{self.total_energy:.2f} mJ",
            transform=self.ax.transAxes,
            ha='right', va='top', fontsize=12,
            bbox=dict(facecolor='white', alpha=0.8)
        )
        self.ax.set_xlabel("Time (s)", fontsize=14)
        self.ax.set_ylabel("Power (mW)", fontsize=14)
        self.ax.grid(True)
        plot_layout.addWidget(toolbar)
        plot_layout.addWidget(self.canvas)
        layout.addWidget(plot_widget)
        self.data_len = len(self.centered_time)
        slider_widget = QWidget()
        slider_layout = QVBoxLayout(slider_widget)
        start_row = QHBoxLayout()
        start_label = QLabel("Start:")
        self.start_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_slider.setRange(0, self.data_len - 2)
        self.start_slider.setValue(0)
        self.start_slider.valueChanged.connect(self.on_slider_change)
        self.start_val_lbl = QLabel("0")
        start_row.addWidget(start_label)
        start_row.addWidget(self.start_slider)
        start_row.addWidget(self.start_val_lbl)
        slider_layout.addLayout(start_row)
        end_row = QHBoxLayout()
        end_label = QLabel("End:")
        self.end_slider = QSlider(Qt.Orientation.Horizontal)
        self.end_slider.setRange(1, self.data_len - 1)
        self.end_slider.setValue(self.data_len - 1)
        self.end_slider.valueChanged.connect(self.on_slider_change)
        self.end_val_lbl = QLabel(str(self.data_len - 1))
        end_row.addWidget(end_label)
        end_row.addWidget(self.end_slider)
        end_row.addWidget(self.end_val_lbl)
        slider_layout.addLayout(end_row)
        layout.addWidget(slider_widget)
        button_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_view)
        save_btn = QPushButton("Save Plot")
        save_btn.clicked.connect(self.save_plot)
        # New Interactive Plot button:
        interactive_btn = QPushButton("Interactive Plot")
        interactive_btn.clicked.connect(self.show_interactive_plot)
        close_btn = QPushButton("Close All")
        close_btn.clicked.connect(self.close_all)
        button_layout.addWidget(reset_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(interactive_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def on_slider_change(self):
        start = self.start_slider.value()
        end = self.end_slider.value()
        if start >= end:
            return
        self.start_val_lbl.setText(str(start))
        self.end_val_lbl.setText(str(end))
        t = self.centered_time[start:end] - self.centered_time[start]
        p = self.power[start:end]
        self.line.set_data(t, p)
        self.ax.relim()
        self.ax.autoscale_view()
        energy = np.trapz(p / 1000, t) * 1000  # Integration: power (W) -> energy (mJ)
        self.energy_text.set_text(f"{energy:.2f} mJ")
        self.canvas.draw()

    def reset_view(self):
        self.start_slider.setValue(0)
        self.end_slider.setValue(self.data_len - 1)

    def save_plot(self):
        save_dir = self.folder_path / "plots"
        save_dir.mkdir(exist_ok=True)
        name = f"{self.file_info['filename']}_trim_{self.start_slider.value()}_{self.end_slider.value()}"
        self.fig.savefig(save_dir / f"{name}.png", dpi=300, bbox_inches='tight')
        self.fig.savefig(save_dir / f"{name}.pdf", bbox_inches='tight')
        print(f"Plot saved to {save_dir}/{name}")
        print(f"Mean Power: {np.mean(self.power[self.start_slider.value():self.end_slider.value()])} mW")

    def show_interactive_plot(self):
        # Get current slider values
        start = self.start_slider.value()
        end = self.end_slider.value()
        if start >= end:
            return
        # Trim the data based on the slider positions
        t = self.centered_time[start:end] - self.centered_time[start]
        p = self.power[start:end]
        # Create a Plotly figure with the trimmed data
        fig = go.Figure(data=go.Scatter(x=t, y=p, mode='lines'))
        fig.update_layout(
            title="Interactive Power Plot",
            xaxis_title="Time (s)",
            yaxis_title="Power (mW)"
        )
        fig.show()

    def close_all(self):
        global close_all
        close_all = True
        QApplication.quit()

# ======================
# Main Function
# ======================
def main():
    app = QApplication(sys.argv)
    default_folder = get_script_root()
    initial_prefs = load_or_create_preferences(default_folder)
    pref_editor = PreferenceEditor(default_folder, initial_prefs)
    pref_editor.show()
    app.exec()
    folder = pref_editor.selected_folder
    prefs = pref_editor.preferences

    # Calculate offsets (in volts) from user-defined divisions:
    OFFSET_CH1 = prefs['CH1_OFFSET_DIVS'] * prefs['CH1_V_PER_DIV']
    OFFSET_CH2 = prefs['CH2_OFFSET_DIVS'] * prefs['CH2_V_PER_DIV']
    R = prefs['R']
    power_formula_str = prefs['power_formula']

    csv_files = list(folder.glob('*.csv'))
    if not csv_files:
        print("No CSV files found in the folder.")
        return

    for file in csv_files:
        if close_all:
            break
        try:
            print(f"\nProcessing file: {file.name}")
            processor = CSVProcessor(file)
            CH1 = processor.voltage_data['CH1']
            CH2 = processor.voltage_data['CH2']
            local_vars = {
                'CH1': CH1,
                'CH2': CH2,
                'OFFSET_CH1': OFFSET_CH1,
                'OFFSET_CH2': OFFSET_CH2,
                'R': R
            }
            # Evaluate the power formula (in Watts) without extra division.
            power_W = eval(power_formula_str, {}, local_vars)
            power_mW = power_W * 1e3  # Convert to mW
            energy_mJ = np.trapz(power_W, processor.time) * 1000
            file_info = {'filename': file.name, 'trim_start': 0, 'trim_end': len(processor.time)}
            window = PlotWindow(file_info, processor, power_mW, folder, energy_mJ)
            window.show()
            app.exec()
        except Exception as e:
            logging.error(f"Error processing {file.name}: {e}")
            continue

if __name__ == "__main__":
    main()
