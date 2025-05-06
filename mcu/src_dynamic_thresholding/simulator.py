import sys
import os
import numpy as np
import pandas as pd
import pyqtgraph as pg
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer

# ======================
# Helper: parse units
# ======================
def parse_value(value_str: str) -> float:
    s = value_str.strip().lower()
    try:
        if s.endswith('mv'):
            return float(s[:-2]) * 1e-3
        if s.endswith('v'):
            return float(s[:-1])
        if s.endswith('us'):
            return float(s[:-2]) * 1e-6
        if s.endswith('s'):
            return float(s[:-1])
        return float(s)
    except:
        return 0.0

# ======================
# CSV Processor
# ======================
class CSVProcessor:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.time = None        # seconds
        self.power = None       # watts
        self.dt = None          # sample interval
        self._process_file()

    def _process_file(self):
        # Read 7-line header
        meta = {}
        with open(self.file_path, 'r') as f:
            for _ in range(7):
                line = f.readline().strip()
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    key = parts[0].rstrip(':').lower()
                    meta[key] = parts[1:]
        # Load CSV data rows
        df = pd.read_csv(self.file_path, skiprows=8)
        # Determine time axis
        if 'time interval' in meta:
            self.dt = parse_value(meta['time interval'][0])
            n = len(df)
            self.time = np.arange(n) * self.dt
        else:
            # assume first column is time
            t0 = df.iloc[:,0].to_numpy(dtype=float)
            self.time = t0
            self.dt = float(self.time[1] - self.time[0])
        # Extract ADC to voltage
        vadc = meta.get('voltage per adc value', ['1','1'])
        v1_per_adc = parse_value(vadc[0])
        v2_per_adc = parse_value(vadc[1])
        att = meta.get('probe attenuation', ['1','1'])
        att1 = float(att[0].rstrip('X'))
        att2 = float(att[1].rstrip('X'))
        ch1 = df.iloc[:,1].to_numpy(dtype=float) * att1 * v1_per_adc
        ch2 = df.iloc[:,2].to_numpy(dtype=float) * att2 * v2_per_adc
        # Compute power: (V2 - V1)*I, where I=V1/R
        R = float(meta.get('r', [100.54])[0])
        diff = ch2 - ch1
        current = ch1 / R
        p = diff * current
        # clamp negative
        self.power = np.clip(p, 0.0, None)

# ======================
# Simulator Window
# ======================
class Simulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Capacitor Simulator')
        self.resize(800, 600)
        self.processor = None
        # Simulation params
        self.fps = 60
        self.win_dur = 10.0         # display last 10s
        self.C = 1e-3               # 1 mF
        self.Vmax = 4.5
        self.Vcut = 3.6
        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self._build_ui()

    def _build_ui(self):
        w = QWidget(); vlay = QVBoxLayout(w)
        # Power plot (mW)
        self.plot_p = pg.PlotWidget()
        self.plot_p.setTitle('Power Profile (mW)')
        self.curve_p = self.plot_p.plot(pen='y')
        self.plot_p.setLabel('left','Power','mW'); self.plot_p.setLabel('bottom','Time','s')
        vlay.addWidget(self.plot_p)
        # Voltage plot
        self.plot_v = pg.PlotWidget()
        self.plot_v.setTitle('Capacitor Voltage (V)')
        self.curve_v = self.plot_v.plot(pen='c')
        self.plot_v.addLine(y=self.Vcut, pen=pg.mkPen(style=Qt.PenStyle.DashLine))
        self.plot_v.setLabel('left','Voltage','V'); self.plot_v.setLabel('bottom','Time','s')
        vlay.addWidget(self.plot_v)
        # Crop sliders
        hlay = QHBoxLayout()
        hlay.addWidget(QLabel('Start'))
        self.sl_start = QSlider(Qt.Orientation.Horizontal)
        self.sl_start.valueChanged.connect(self._update_crop)
        hlay.addWidget(self.sl_start)
        hlay.addWidget(QLabel('End'))
        self.sl_end = QSlider(Qt.Orientation.Horizontal)
        self.sl_end.valueChanged.connect(self._update_crop)
        hlay.addWidget(self.sl_end)
        vlay.addLayout(hlay)
        # Controls
        hlay2 = QHBoxLayout()
        btn_load = QPushButton('Load CSV'); btn_load.clicked.connect(self._load)
        hlay2.addWidget(btn_load)
        hlay2.addWidget(QLabel('Charge mW'))
        self.sl_charge = QSlider(Qt.Orientation.Horizontal)
        self.sl_charge.setRange(0,2000); self.sl_charge.setValue(0)
        hlay2.addWidget(self.sl_charge)
        self.lbl_charge = QLabel('0 mW')
        self.sl_charge.valueChanged.connect(lambda v: self.lbl_charge.setText(f"{v} mW"))
        hlay2.addWidget(self.lbl_charge)
        self.btn_start = QPushButton('Start'); self.btn_start.clicked.connect(self._toggle)
        hlay2.addWidget(self.btn_start)
        vlay.addLayout(hlay2)
        self.setCentralWidget(w)

    def _load(self):
        fn,_ = QFileDialog.getOpenFileName(self,'Select CSV','', 'CSV Files (*.csv)')
        if not fn: return
        self.processor = CSVProcessor(Path(fn))
        t = self.processor.time; n = len(t)
        self.sl_start.setRange(0,n-2); self.sl_end.setRange(1,n-1)
        self.sl_start.setValue(0); self.sl_end.setValue(n-1)
        self._update_crop()

    def _update_crop(self):
        if not self.processor: return
        s = self.sl_start.value(); e = self.sl_end.value()
        if s>=e: return
        t = self.processor.time[s:e] - self.processor.time[s]
        p = self.processor.power[s:e] * 1e3
        self.tcrop = t; self.pcrop = p; self.trace_len = t[-1]
        self.curve_p.setData(t,p)
        self.plot_p.setXRange(max(0,t[-1]-self.win_dur), t[-1])
        self._reset_sim()

    def _reset_sim(self):
        self.sim_t = 0.0; self.V = self.Vmax
        self.t_hist=[]; self.V_hist=[]
        self.timer.setInterval(int(1000/self.fps)); self.curve_v.clear()

    def _toggle(self):
        if not hasattr(self,'tcrop'): return
        if self.timer.isActive(): self.timer.stop(); self.btn_start.setText('Start')
        else: self._reset_sim(); self.timer.start(); self.btn_start.setText('Stop')

    def _step(self):
        dt = 1/self.fps; self.sim_t+=dt
        t_mod = self.sim_t % self.trace_len; idx = int(t_mod/self.processor.dt)
        pd = self.pcrop[idx] if self.V>self.Vcut else 0.0
        pc = self.sl_charge.value()
        net = (pc-pd)*1e-3
        dV = net*dt/(self.C*self.V) if self.V>0 else 0
        self.V = np.clip(self.V+dV, self.Vcut, self.Vmax)
        self.t_hist.append(self.sim_t); self.V_hist.append(self.V)
        th = np.array(self.t_hist); vh = np.array(self.V_hist)
        mask = th>=self.sim_t-self.win_dur
        self.curve_v.setData(th[mask], vh[mask])

if __name__=='__main__':
    app = QApplication(sys.argv)
    sim = Simulator(); sim.show(); sys.exit(app.exec())
