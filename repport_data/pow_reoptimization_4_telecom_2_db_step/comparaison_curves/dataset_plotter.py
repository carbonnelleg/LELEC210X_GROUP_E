import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import os

# Make the scrypt current environment be the script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# dBm : [Peak Power, Energy]
dataset = {
    0: [16.5, 2.31],
    -2: [15.5, 2.18],
    -4: [14.7, 2.09],
    -6: [14, 1.98],
    -8: [13.3, 1.89],
    -10: [13, 1.81],
    -12: [12.2, 1.74],
    -14: [12, 1.73],
    -16: [11.8, 1.71],
    -18: [11.5, 1.68],
    -20: [11, 1.60],
    -22: [11.1, 1.62],
    -24: [10.8, 1.59],
    -26: [10.85, 1.59],
    -28: [10.7, 1.56],
    -30: [10.9, 1.57],
    -40: [11, 1.6],
    -50: [20.5,3.39]
}

# Exclude outlier from fitting
fit_keys = [k for k in dataset if k > -45]
x_fit = np.array(fit_keys)
y_peak_fit = np.array([dataset[k][0] for k in fit_keys])
y_energy_fit = np.array([dataset[k][1] for k in fit_keys])

x_all = np.array(sorted(dataset.keys()))
y_peak_all = np.array([dataset[k][0] for k in sorted(dataset)])
y_energy_all = np.array([dataset[k][1] for k in sorted(dataset)])

# Updated exponential function
def exp_func(x, a, b, c):
    return a + b * np.exp(c * x)

# Fit data with better starting guess and more iterations
try:
    popt_peak, _ = curve_fit(exp_func, x_fit, y_peak_fit, p0=(1, 1, 1), maxfev=10000)
except RuntimeError as e:
    print("Peak Power Fit Failed:", e)
    popt_peak = [np.nan, np.nan, np.nan]

try:
    popt_energy, _ = curve_fit(exp_func, x_fit, y_energy_fit, p0=(1, 1, 1), maxfev=10000)
except RuntimeError as e:
    print("Energy Fit Failed:", e)
    popt_energy = [np.nan, np.nan, np.nan]

# Generate smooth curve
x_smooth = np.linspace(min(x_all), max(x_all), 300)
y_peak_smooth = exp_func(x_smooth, *popt_peak)
y_energy_smooth = exp_func(x_smooth, *popt_energy)

# Plot
fig, ax1 = plt.subplots()

ax1.plot(x_all, y_peak_all, 'bo-', label='Peak Power (data)', alpha=0.8)
ax1.plot(x_smooth, y_peak_smooth, 'b--', label=f'Peak Power Fit: {popt_peak[0]:.2f} + {popt_peak[1]:.2f}e^({popt_peak[2]:.3f}x)', alpha=0.5)
ax1.set_xlabel('dBm')
ax1.set_ylabel('Peak Power (mW)', color='b')
ax1.tick_params(axis='y', labelcolor='b')
ax1.yaxis.set_major_locator(plt.MaxNLocator(integer=False))
ax1.invert_xaxis()

ax2 = ax1.twinx()
ax2.plot(x_all, y_energy_all, 'ro-', label='Energy (data)', alpha=0.8)
ax2.plot(x_smooth, y_energy_smooth, 'r--', label=f'Energy Fit: {popt_energy[0]:.2f} + {popt_energy[1]:.2f}e^({popt_energy[2]:.3f}x)', alpha=0.5)
ax2.set_ylabel('Energy (mJ)', color='r')
ax2.tick_params(axis='y', labelcolor='r')

plt.title('Peak Power and Energy vs dBm')
plt.grid()

# Legends
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

plt.tight_layout()
plt.savefig('telecom_power_plot.png')
plt.show()