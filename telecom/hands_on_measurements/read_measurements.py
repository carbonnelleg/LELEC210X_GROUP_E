import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import re
from typing import Tuple, List, Optional
from telecom.hands_on_simulation import load_simdata

def parse_datafile(filename: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parses the given data file and extracts noise metrics and packet metrics into DataFrames.

    Parameters
    ----------
    filename: str
        Path to the data file.

    Returns
    -------
    df_noise: pd.DataFrame
        DataFrame containing noise estimation metrics.
    df_packets: pd.DataFrame
        DataFrame containing packet metrics.
    """
    noise_data = []
    packet_data = []
    current_packet = {}

    with open(filename, "r") as file:
        for line in file:
            line = line.strip()

            # Match noise estimation lines
            noise_match = re.match(r"noise_est=(.*), dc_offset=(.*), n_samples=(\d+)", line)
            if noise_match:
                noise_data.append({
                    "noise_est": float(noise_match.group(1)),
                    "dc_offset": float(noise_match.group(2)),
                    "n_samples": int(noise_match.group(3))
                })
                continue

            # Match mean noise power
            mean_noise_match = re.match(r"mean_noise_power=(.*)", line)
            if mean_noise_match:
                noise_data.append({
                    "noise_est": float(mean_noise_match.group(1)),
                    "dc_offset": None,
                    "n_samples": None
                })
                continue

            # Match packet information
            packet_match = re.match(r"packet_number=(\d+), correct=(\w+), payload=\[(.*)\]", line)
            if packet_match:
                # Save the previous packet data if not empty
                if current_packet:
                    packet_data.append(current_packet)
                
                payload_str = packet_match.group(3)
                payload = np.array(list(map(int, payload_str.split(',')))) if payload_str else np.array([])

                payload_length = len(payload)
                if payload_length > 0:
                    expected_payload = np.arange(payload_length)  # Expected sequence
                    bit_errors = np.bitwise_xor(payload, expected_payload)
                    ber = np.sum(np.unpackbits(bit_errors.astype(np.uint8))) / (payload_length * 8)  # Total bits
                else:
                    ber = np.nan  # Assign NaN if no payload is present

                current_packet = {
                    "packet_number": int(packet_match.group(1)),
                    "correct": packet_match.group(2) == "True",
                    "BER": ber
                }
                continue

            # Match CFO and STO
            cfo_sto_match = re.match(r"CFO=(.*), STO=(.*)", line)
            if cfo_sto_match:
                current_packet["CFO"] = float(cfo_sto_match.group(1))
                current_packet["STO"] = int(cfo_sto_match.group(2))
                continue

            # Match SNR and power levels
            snr_power_match = re.match(r"SNRdB=(.*), RXPdB=(.*), TXPdB=(.*)", line)
            if snr_power_match:
                current_packet["SNR"] = float(snr_power_match.group(1))
                if np.isnan(current_packet["SNR"]):
                    current_packet["approx_SNR"] = np.nan
                else:
                    current_packet["approx_SNR"] = round(float(snr_power_match.group(1)), 0)
                current_packet["RXP"] = float(snr_power_match.group(2))
                current_packet["TXP"] = float(snr_power_match.group(3))

    # Append last packet
    if current_packet:
        packet_data.append(current_packet)

    # Convert lists to Pandas DataFrames
    df_noise = pd.DataFrame(noise_data)
    df_packets = pd.DataFrame(packet_data)

    return df_noise, df_packets


def plot_cfo_histogram(
    cfo_values: np.array, correct_flags: np.array,
    bin_width: float = 10., std_threshold: float = 0.,
    save: str = None, log: bool = True
) -> List[int]:
    """
    Plot a histogram of the Carrier Frequency Offset (CFO) with bin colors
    representing packet accuracy. Red bins have more errored packets, 
    green bins have more correct packets.

    Parameters
    ----------
    cfo_values : np.array
        Array of CFO values.
    correct_flags : np.array
        Boolean array indicating whether each packet was correctly received (True) or not (False).
    bin_width : float, optional
        The width of each bin in the histogram. Default is 10.
    std_threshold : float, optional
        The number of standard deviations from the mean to use as a threshold for excluding outliers.
        A value of 0 includes all data points. Default is 0.
    save : str, optional
        If provided, the histogram will be saved as an image in the "graphs/" directory relative 
        to the script location. Default is None (no saving).
    log : bool, optional
        If True, the y-axis will be set to a logarithmic scale. Default is True.

    Returns
    -------
    packet_indices : List[int]
        Indices of packets that are included in the histogram after filtering based on the 
        standard deviation threshold.
    """
    cfo_values = np.asarray(cfo_values)
    correct_flags = np.asarray(correct_flags)

    if cfo_values.size == 0:
        raise ValueError("CFO values array is empty.")

    # Compute mean and standard deviation
    median_cfo = np.median(cfo_values)
    std_cfo = np.std(cfo_values)

    # Filter values within threshold
    mask = np.ones_like(cfo_values, dtype=bool)
    if std_threshold:
        mask = (cfo_values >= median_cfo - std_threshold * std_cfo) & (cfo_values <= median_cfo + std_threshold * std_cfo)

    filtered_cfo = cfo_values[mask]
    filtered_correct_flags = correct_flags[mask]
    new_mean_cfo = np.mean(filtered_cfo)

    if filtered_cfo.size == 0:
        print("No data remaining after filtering.")
        return []
    
    packet_indices = np.where(mask)[0].tolist()

    # Define bins
    min_cfo, max_cfo = np.min(filtered_cfo), np.max(filtered_cfo)
    bins = np.arange(min_cfo, max_cfo + bin_width, bin_width)

    # Assign bins to CFO values
    bin_indices = np.digitize(filtered_cfo, bins) - 1  # Get bin index for each CFO

    # Count correct and incorrect packets in each bin
    bin_counts = {i: {"correct": 0, "incorrect": 0} for i in range(len(bins) - 1)}
    
    for i, correct in zip(bin_indices, filtered_correct_flags):
        if correct:
            bin_counts[i]["correct"] += 1
        else:
            bin_counts[i]["incorrect"] += 1
    
    # Compute total counts and correct ratio per bin
    total_packets = np.array([bin_counts[i]["correct"] + bin_counts[i]["incorrect"] for i in range(len(bins) - 1)])
    correct_ratios = np.array([bin_counts[i]["correct"] / total_packets[i] if total_packets[i] > 0 else 0 for i in range(len(bins) - 1)])
    
    # Define colormap (red = errored, green = correct)
    cmap = mcolors.LinearSegmentedColormap.from_list("accuracy_cmap", ["red", "green"])
    bin_colors = cmap(correct_ratios)  # Map correct ratio to color

    # Plot histogram with colors
    fig, ax = plt.subplots()
    ax.bar(bins[:-1], total_packets, width=bin_width, color=bin_colors, label="Estimated CFO distribution")

    ax.set_xlabel("Estimated CFO")
    ax.set_ylabel("Frequency")
    ax.set_title(f"Histogram of Estimated CFO (Filtered: ±{std_threshold} std)")
    ax.legend()
    ax.grid(True)

    if log:
        ax.set_yscale("log")

    fig.colorbar(plt.cm.ScalarMappable(cmap=cmap), ax=ax, label="Correct Packet Ratio")

    if save is not None:
        fig.savefig(__file__ + f"/../graphs/{save}", dpi=200)

    plt.show()

    return packet_indices


def plot_ber_per_vs_snr(
    snr_data: List[np.array], 
    ber_data: List[np.array], 
    per_data: List[np.array], 
    labels: Optional[List[str]] = None,
    save: Optional[Tuple[str, str]] = None
) -> Tuple[plt.Figure, plt.Figure]:
    """
    Plots two graphs:
    1. Bit Error Rate (BER) as a function of SNR.
    2. Packet Error Rate (PER) as a function of SNR.

    Multiple datasets can be plotted simultaneously.

    Parameters
    ----------
    snr_data : List[np.array]
        List of arrays containing SNR values.
    ber_data : List[np.array]
        List of arrays containing BER values corresponding to SNR values.
    per_data : List[np.array]
        List of arrays containing PER values corresponding to SNR values.
    labels : List[str], optional
        List of labels for each dataset in the plots.
    save : Tuple[str, str], optional
        If provided, saves the figures to the specified file paths (BER first, then PER).
    
    Returns
    -------
    fig_ber : plt.Figure
    fig_per : plt.Figure

    Raises
    ------
    ValueError
        If the input lists are empty or have mismatched lengths.
    """
    if not (len(snr_data) == len(ber_data) == len(per_data)):
        raise ValueError("snr_data, ber_data, and per_data must have the same length.")
    
    num_datasets = len(snr_data)
    if num_datasets == 0:
        raise ValueError("No data provided for plotting.")

    # Initialize plots
    fig_ber, ax_ber = plt.subplots()
    fig_per, ax_per = plt.subplots()

    # Default labels if none are provided
    if labels is None:
        labels = [f"Dataset {i+1}" for i in range(num_datasets)]

    for i, (snr_values, ber_values, per_values, label) in enumerate(zip(snr_data, ber_data, per_data, labels)):
        snr_values = np.asarray(snr_values)
        ber_values = np.asarray(ber_values)
        per_values = np.asarray(per_values)

        if snr_values.size == 0:
            raise ValueError(f"SNR values array is empty for dataset {label}.")

        # Compute average BER and PER per SNR group
        unique_snr = np.unique(snr_values)
        avg_ber = np.array([np.mean(ber_values[snr_values == snr]) for snr in unique_snr])
        avg_per = np.array([np.mean(per_values[snr_values == snr]) for snr in unique_snr])

        # Plot BER vs. SNR
        ax_ber.plot(unique_snr, avg_ber, "-s", label=label)

        # Plot PER vs. SNR
        ax_per.plot(unique_snr, avg_per, "-o", label=label)

    # Formatting BER plot
    ax_ber.set_xlabel("SNR (dB)")
    ax_ber.set_ylabel("Bit Error Rate (BER)")
    ax_ber.set_yscale("log")
    ax_ber.set_title("BER vs. Approximate SNR")
    ax_ber.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax_ber.legend()

    # Formatting PER plot
    ax_per.set_xlabel("SNR (dB)")
    ax_per.set_ylabel("Packet Error Rate (PER)")
    ax_per.set_yscale("log")
    ax_per.set_title("PER vs. Approximate SNR")
    ax_per.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax_per.legend()

    # Save figures if requested
    if save is not None:
        if len(save) != 2 or not all(isinstance(f, str) for f in save):
            raise ValueError("Expected 'save' to be a tuple of two valid file paths.")
        ber_save, per_save = save
        fig_ber.savefig(__file__ + f"/../graphs/{ber_save}", dpi=200)
        fig_per.savefig(__file__ + f"/../graphs/{per_save}", dpi=200)

    plt.show()

    return fig_ber, fig_per


import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional

def plot_false_miss_detection_vs_txp(
    data: List[Tuple[np.array, np.array]],
    labels: Optional[List[str]] = None,
    expected_packets: int = 200,
    ber_threshold: float = 0.1,
    save: Optional[str] = None
) -> plt.Figure:
    """
    Plots the false detected packet rate and miss detected packet rate as a function of TXP.
    
    Parameters
    ----------
    data : List[Tuple[np.array, np.array]]
        List of (txp_values, ber_values) doublets. Each doublet corresponds to one dataset.
    labels : List[str], optional
        List of labels for each dataset in the plots.
    expected_packets : int, optional
        The expected number of packets per TXP (default is 200).
    ber_threshold : float, optional
        BER threshold below which a packet is considered a true packet (default is 0.1).
    save : str, optional
        If provided, saves the figure to the specified file path.

    Returns
    -------
    fig : plt.Figure
        The generated matplotlib figure.
    """
    fig, ax = plt.subplots()

    # Define colors for datasets
    colors = ["red", "blue", "green", "purple", "orange", "cyan"]  # Cycle through colors

    # Default labels if none are provided
    num_datasets = len(data)
    if labels is None:
        labels = [f"Dataset {i+1}" for i in range(num_datasets)]

    for i, (txp_values, ber_values) in enumerate(data):
        if txp_values.size == 0:
            raise ValueError(f"TXP values array in dataset {i} is empty.")

        # Filter out TXP = 0
        valid_indices = txp_values != 0.0
        txp_values = txp_values[valid_indices]
        ber_values = ber_values[valid_indices]

        unique_txp = np.unique(txp_values)
        false_detected_rate = []
        miss_detected_rate = []

        for txp in unique_txp:
            ber_subset = ber_values[txp_values == txp]  # Select BER values for this TXP
            received_count = len(ber_subset)  # Number of received packets

            true_detected = np.sum(ber_subset < ber_threshold)  # Correctly received packets
            false_detected = received_count - true_detected  # Packets falsely detected
            missed_packets = expected_packets - received_count  # Packets that were never received

            false_detected_rate.append(false_detected / expected_packets)
            miss_detected_rate.append(missed_packets / expected_packets)

        color = colors[i % len(colors)]  # Assign a unique color to the dataset

        # Plot False Detection Rate (Solid Line)
        ax.plot(unique_txp, false_detected_rate, "--", label=f"{labels[i]} - False Detection", color=color)

        # Plot Miss Detection Rate (Dashed Line)
        ax.plot(unique_txp, miss_detected_rate, "-", label=f"{labels[i]} - Miss Detection", color=color)

    ax.set_xlabel("TXP")
    ax.set_ylabel("Detection Rate")
    ax.set_title("False and Miss Detection Rate vs. TXP")
    ax.set_ylim(0, 1)  # Rates are between 0 and 1
    ax.grid(True, linestyle="--", linewidth=0.5)
    ax.legend()

    # Save the figure if requested
    if save is not None:
        fig.savefig(__file__ + f"/../graphs/{save}", dpi=200)

    plt.show()
    
    return fig



def main():

    # Example usage
    filename = __file__ + "/../data/eval_radio_measurements_t20250322_130538.txt"
    df_noise_1, df_packets_1 = parse_datafile(filename)
    filename = __file__ + "/../data/eval_radio_measurements_t20250322_151715.txt"
    df_noise_2, df_packets_2 = parse_datafile(filename)

    # Plot CFO histograms
    cfo = df_packets_1["CFO"]
    correct = df_packets_1["correct"]
    plot_cfo_histogram(cfo, correct, bin_width=200.0, save="CFO_hist_no_filt_att.png")
    valid_packets_1 = plot_cfo_histogram(cfo, correct,
                                       std_threshold=2.0, save="CFO_hist_filt_att.png",
                                       log=False)
    cfo = df_packets_2["CFO"]
    correct = df_packets_2["correct"]
    plot_cfo_histogram(cfo, correct, bin_width=200.0, save="CFO_hist_no_filt_no_att.png")
    valid_packets_2 = plot_cfo_histogram(cfo, correct,
                                       std_threshold=0.2, save="CFO_hist_filt_no_att.png",
                                       log=False)
    
    # Plot BER vs SNR plot
    snr_1 = df_packets_1.iloc[valid_packets_1]["approx_SNR"]
    ber_1 = df_packets_1.iloc[valid_packets_1]["BER"]
    per_1 = ~df_packets_1.iloc[valid_packets_1]["correct"]
    snr_2 = df_packets_2.iloc[valid_packets_2]["approx_SNR"]
    ber_2 = df_packets_2.iloc[valid_packets_2]["BER"]
    per_2 = ~df_packets_2.iloc[valid_packets_2]["correct"]

    # Compare to simulation_0039
    sim_df = load_simdata.load_simulation(39)
    plot_ber_per_vs_snr([snr_1, snr_2, sim_df["SNR_e [dB]"]],
                        [ber_1, ber_2, sim_df["BER"]],
                        [per_1, per_2, sim_df["PER"]],
                        labels=["With attenuator", "Without attenuator", "Simulation"],
                        save=("BER_SNR.png", "PER_SNR.png"))
    
    plot_false_miss_detection_vs_txp(
        [(df_packets_1["TXP"], df_packets_1["BER"]),
         (df_packets_2["TXP"], df_packets_2["BER"])],
        labels=("With attenuator", "Without attenuator"),
        save="Detection_rate.png"
        )

if __name__ == "__main__":
    main()