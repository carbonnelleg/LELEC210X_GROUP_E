import pandas as pd
import numpy as np
from matplotlib.widgets import Slider, Button
import sys
from tkinter import filedialog
import os

root_dir = os.path.dirname(os.path.abspath(__file__))

import matplotlib.pyplot as plt


CHANNEL_TO_USE = 1

# Read CSV file
def read_data(file_path):
    try:
        data = pd.read_csv(file_path)
        time = pd.to_numeric(data.iloc[:, 0], errors='coerce').values  # Column 0 as time
        values = pd.to_numeric(data.iloc[:, CHANNEL_TO_USE], errors='coerce').values  # Column 2 as values
        # Remove NaN values
        mask = ~np.isnan(time) & ~np.isnan(values)
        return time[mask], values[mask]
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None, None

# Main plotting function with trimming capability
def plot_with_trimming(file_path):
    time, values = read_data(file_path)
    
    if time is None or values is None:
        return
    
    # Correct time to seconds
    TIME_STEP = 400e-6  # 400 us
    time = time * TIME_STEP

    fig, ax = plt.subplots(figsize=(10, 6))
    # Initial plot
    plot_line, = ax.plot(time, values)
    
    # Add grid and show x-axis (hide y-axis)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(True)
    ax.yaxis.set_visible(False)
    ax.xaxis.set_visible(True)
    ax.set_xlabel('Time (s)')
    
    # Time limits
    t_min = min(time)
    t_max = max(time)
    
    # Add sliders for trimming - positioned lower
    ax_start = plt.axes([0.25, 0.07, 0.65, 0.03])
    ax_end = plt.axes([0.25, 0.02, 0.65, 0.03])
    
    start_slider = Slider(ax_start, 'Start Time', t_min, t_max, valinit=t_min)
    end_slider = Slider(ax_end, 'End Time', t_min, t_max, valinit=t_max)
    
    # Add save button
    ax_save = plt.axes([0.8, 0.12, 0.1, 0.04])
    save_button = Button(ax_save, 'Save')
    
    def save_figure(event):
        # Get current trimmed data
        start = start_slider.val
        end = end_slider.val
        mask = (time >= start) & (time <= end)
        
        # Create a new figure for saving (without controls)
        save_fig, save_ax = plt.subplots(figsize=(10, 6))
        
        # Get trimmed data
        temp_x = time[mask] - time[mask][0]  # Normalize x-axis to start from 0
        temp_y = values[mask]
        
        # Plot with same style
        save_ax.plot(temp_x, temp_y)
        save_ax.grid(True, linestyle='--', alpha=0.7)
        save_ax.spines['left'].set_visible(False)
        save_ax.spines['top'].set_visible(False)
        save_ax.spines['right'].set_visible(False)
        save_ax.spines['bottom'].set_visible(True)
        save_ax.yaxis.set_visible(False)
        save_ax.xaxis.set_visible(True)
        save_ax.set_xlabel('Time (s)')
        
        # Ask for save location
        save_path = filedialog.asksaveasfilename(
            defaultextension='.png',
            filetypes=[('PNG files', '*.png'), ('All files', '*.*')],
            title="Save Plot As"
        )
        
        if save_path:
            save_fig.savefig(save_path, bbox_inches='tight', dpi=300)
            removed_extension = os.path.splitext(save_path)[0]
            save_fig.savefig(removed_extension + ".pdf", bbox_inches='tight')
            plt.close(save_fig)
            print(f"Plot saved to {save_path}")
    
    save_button.on_clicked(save_figure)
    
    def update(_):  # Renamed parameter since it's unused
        start = start_slider.val
        end = end_slider.val
        
        if start >= end:
            return
        
        # Get the data in the range
        mask = (time >= start) & (time <= end)
        temp_x = time[mask]
        temp_y = values[mask]
        
        # Normalize x-values to start from 0
        temp_x = temp_x - temp_x[0]
        
        plot_line.set_xdata(temp_x)
        plot_line.set_ydata(temp_y)        
        ax.set_xlim(0, temp_x[-1])
        ax.grid(True, linestyle='--', alpha=0.7)  # Ensure grid remains after updates
        fig.canvas.draw_idle()
    
    start_slider.on_changed(update)
    end_slider.on_changed(update)
    
    # Initialize the plot with normalized x-axis
    update(None)
    
    plt.show()

if __name__ == "__main__":
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # open file dialog
        default_path = root_dir
        file_path = filedialog.askopenfilename(initialdir=default_path, title="Select CSV file")
    
    plot_with_trimming(file_path)