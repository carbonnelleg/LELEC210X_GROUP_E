import os
import json
import numpy as np
from glob import glob
import argparse

root_dir = os.path.dirname(os.path.abspath(__file__))

import matplotlib.pyplot as plt

def load_json_files(directory):
    """Load all json files from the given directory."""
    json_files = glob(os.path.join(directory, "*.json"))
    data = {}
    
    for file_path in json_files:
        filename = os.path.basename(file_path)
        with open(file_path, 'r') as file:
            data[filename] = json.load(file)
            
    return data

def plot_bar_graphs(data, output_dir="./plots"):
    """Generate bar graphs from the loaded JSON data."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for filename, values in data.items():
        graph_title = values.get("title", filename.split(".")[0])
        x_label = values.get("xlabel", "Optimization")
        y_label = values.get("ylabel", "# Cycles")
        y = values.get("y", [])
        x = values.get("x", list(range(len(y))))

        fig, ax = plt.subplots()
        ax.bar(x, y)
        ax.set_title(graph_title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_xticks(x)
        ax.set_xticklabels(x)
        # Put the number of cycles on top of each bar
        for i, v in enumerate(y):
            ax.text(i, v, str(v), ha='center', va='bottom')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"{filename}.png"))
        plt.savefig(os.path.join(output_dir, f"{filename}.pdf"))
        plt.close()

def main():
    parser = argparse.ArgumentParser(description='Generate bar graphs from JSON data files')
    parser.add_argument('--input_dir', type=str, default='./data', help='Directory containing JSON files')
    parser.add_argument('--output_dir', type=str, default='./plots', help='Directory to save plots')
    
    # If the paths are relative, make them absolute
    if not os.path.isabs(parser.parse_args().input_dir):
        input_dir = os.path.join(root_dir, parser.parse_args().input_dir)

    if not os.path.isabs(parser.parse_args().output_dir):
        output_dir = os.path.join(root_dir, parser.parse_args().output_dir)

    args = parser.parse_args()
    
    data = load_json_files(input_dir)
    if not data:
        print("No JSON files found in the specified directory!")
        return
        
    plot_bar_graphs(data, output_dir)
    print(f"Plots saved to {output_dir}")

if __name__ == "__main__":
    main()