"""
Read a measurements file generated by eval_limesdr_fpga.py
and plots the PER/SNR curve, plus CFO values.
"""

import sys
import os
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib import cm, colors
import matplotlib as mpl
import numpy as np
import pandas as pd
from telecom.hands_on_simulation import sim, chain


def read_measurements(
    filepath_meas: str, filepath_compl_meas: str = None, num_bytes: int = 50,
    first_bytes: int = None,
    txp: bool = False, distance: bool = False, ber: bool = True
) -> pd.DataFrame:

    expected_payload = np.arange(num_bytes, dtype=np.uint8)
    data = defaultdict(list)
    payload_data = []
    with open(os.path.dirname(__file__)+'/'+filepath_meas) as f:
        for line in f.read().splitlines():
            if line.startswith("CFO"):
                cfo, sto = line.split(",")
                data["cfo"].append(float(cfo.split("=")[1]))
                data["sto"].append(int(sto.split("=")[1]))
            elif line.startswith("SNR"):
                snr, _ = line.split(",")
                data["snr"].append(float(snr.split("=")[1]))
            elif line.startswith("packet"):
                idx, correct, payload = line.split(",", maxsplit=2)
                idx = int(idx.split("=")[1])
                correct = int(correct.split("=")[1] == "True")
                data["indices"].append(idx)
                data["correct"].append(correct)
                payload = list(
                    map(np.uint8, payload.split("=")[1][1:-1].split(",")))
                payload_data.append(payload)
                if ber:
                    ber_value = (
                        np.unpackbits(
                            expected_payload ^ np.array(
                                payload, dtype=np.uint8)
                        ).sum() / (num_bytes*8)
                    )
                    data["ber"].append(ber_value)
                if first_bytes is not None and ber:
                    ber_first_bytes = (
                        np.unpackbits(
                            expected_payload[:first_bytes] ^ np.array(
                                payload, dtype=np.uint8)[:first_bytes]
                        ).sum() / (len(expected_payload[:first_bytes])*8)
                    )
                    data["ber_first_bytes"].append(ber_first_bytes)

    if filepath_compl_meas is not None:
        try:
            with open(os.path.dirname(__file__)+'/'+filepath_compl_meas) as f:
                if txp:
                    data["txp"] = list(
                        np.full_like(data["indices"], np.nan, dtype=float))
                    for line in f.read().splitlines():
                        if line.startswith("TXP:"):
                            txp_value, * \
                                _, idxs = line.replace("TXP:", "").split(" ")
                            txp_value = float(txp_value.replace("dB", ""))
                            idx_begin, idx_end = map(int, idxs.split("-"))
                            data["txp"][idx_begin-1: idx_end] = \
                                list(np.full(idx_end-idx_begin+1, txp_value))
                if distance:
                    data["distance"] = list(
                        np.full_like(data["indices"], np.nan, dtype=float))
                    for line in f.read().splitlines():
                        if line.startswith("DISTANCE:"):
                            distance_value, * \
                                _, idxs = line.replace(
                                    "DISTANCE:", "").split(" ")
                            distance_value = float(
                                distance_value.replace("m", ""))
                            idx_begin, idx_end = map(int, idxs.split("-"))
                            data["distance"][idx_begin-1: idx_end] = \
                                list(np.full(idx_end-idx_begin+1, distance_value))
        except Exception as e:
            print("""
                  Please provide a second argument when calling this script
                  Second argument should be a .txt file with the following information and structure:

                  [complementary_measurements.txt]
                  ...
                  whatever additional information needed
                  ...
                  TXP:-45dB  0001-0004
                  TXP:-42dB  0005-0126
                  ...
                  additional commentary here
                  ...
                  TXP:-12dB  1429-1578
                  TXP:-15    1268-1428
                  ...
                  DISTANCE:1.0m  0001-0004
                  DISTANCE:2m    0005-0126
                  ...
                  additional commentary here
                  ...
                  DISTANCE:3     1429-1578
                  DISTANCE:4.0   1268-1428
                  ...
                  [end of file]

                  Each line begining with 'TXP:' first reads the power in dB (Watt)
                  (no need to write dB but don't write anything else),
                  then a separation with at least 1 space ' ',
                  and then the index of the first and last received packet at that power
                  separated by a '-'
                  Each line begining with 'DISTANCE:' first reads the distance in meter
                  (no need to write m but don't write anything else),
                  then a separation with at least 1 space ' ',
                  and then the index of the first and last received packet at that distance
                  separated by a '-'

                  """)
            raise e
    df = pd.DataFrame.from_dict(data)
    df.set_index("indices", drop=True, inplace=True)
    payload_df = pd.DataFrame(payload_data)
    payload_df.set_index(df.index, inplace=True)
    return (df, payload_df)


def plot_BER_vs_byte_pos(payload_df: pd.DataFrame) -> mpl.figure.Figure:

    expected_payload = np.arange(payload_df.shape[0], dtype=np.uint8)
    num_bits = payload_df.shape[0] * 8
    BER = np.zeros(payload_df.shape[1], dtype=float)
    for idx, column in enumerate(payload_df):
        BER[idx] = np.unpackbits(
            payload_df[column] ^ expected_payload[idx]).sum() / num_bits
    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title('Measurements: BER vs Byte position')
    ax.plot(payload_df.columns, BER*100, color='black')
    ax.set_xlabel('Byte position')
    ax.set_ylabel('BER [%]')
    fig.suptitle('BER vs Byte position in packet')
    ax.set_title('across all SNR\'s')
    return fig


def plot_SNRest_vs_CFOest(df: pd.DataFrame, N: int = 16) -> mpl.figure.Figure:

    groups = df.groupby('txp')
    txp_delta = list(groups)[0][0] - list(groups)[1][0]
    cmap = plt.get_cmap('gist_rainbow').resampled(len(groups))
    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title(f'Measurements: SNR est vs CFO est N={N}')
    for i, (txp, txp_df) in enumerate(list(groups)[::-1], start=1):
        c = cmap(range(len(groups)))[len(groups)-i]
        ax.scatter(txp_df['cfo']/1000, txp_df['snr'], s=3,
                   color=c)
        ax.axhline(y=np.nanpercentile(txp_df.loc[:, 'snr'], 50),
                   color=c, linewidth=.5)
    ax.scatter(np.nan, np.nan, color='black', label='Received packet metrics')
    ax.axhline(y=np.nan, color='black', label='Median SNR')
    ax.set_xlabel('CFO estimation [kHz]')
    ax.set_ylabel('SNR estimation [dB]')
    ax.legend(loc=4, fontsize='small')
    ax.set_title(f'N = {N}')
    fig.suptitle('CFO and SNR estimation statistics')
    fig.colorbar(cm.ScalarMappable(cmap=cmap,
                                   norm=colors.Normalize(
                                       vmin=list(groups)[0][0] + txp_delta/2,
                                       vmax=list(groups)[-1][0] - txp_delta/2)),
                 ticks=list(groups.groups.keys()), ax=ax, label='TXP [dBW]')
    return fig


def plot_cfo_hist(
    df: pd.DataFrame, N: int = 16, color: str = None
) -> mpl.figure.Figure:

    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title(f'Measurements: CFO histogram N={N}')
    description = df.groupby("txp").describe()
    df['cfo_dev'] = list(np.zeros_like(df.index, dtype=float))
    for (idx, serie) in df.iterrows():
        if not np.isnan(serie['txp']):
            df.loc[idx, 'cfo_dev'] = serie['cfo'] - \
                description.loc[serie['txp'], ('cfo', 'mean')]
    df.hist(column='cfo_dev', ax=ax)
    ax.patches[-1].set_label(f'N = {N}')
    if color is not None:
        for patch in ax.patches:
            patch.set_color(color)
    ax.legend()
    ax.set_xlabel('Centered CFO estimation [Hz]')
    mean = df['cfo'].mean()
    stdev = np.sqrt(((df['cfo_dev'].array*df['cfo_dev'].array)).mean())
    ax.set_title(f'$\\mu = {mean:.2f} Hz\\;\\;\\;\\;\\sigma = {stdev:.2f} Hz$')
    fig.suptitle('Centered CFO distribution')
    return fig


def plot_BER_vs_SNRest(
    df: pd.DataFrame, drop_extrema: bool = True, drop_last_bytes: bool = False,
    comp_sim: bool = False, SNR_sim: np.ndarray[float] = None,
    BER_sim: list[np.ndarray[float]] = None, labels_sim: list[str] = None
) -> mpl.figure.Figure:

    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title('Measurements: BER vs SNR est')
    if comp_sim:
        for BER, label in zip(BER_sim, labels_sim):
            BER_SNR_sim(SNR_sim, BER, label, fig)
    ax.set_yscale('log')
    description = df.groupby("txp").describe(percentiles=[.05, .5, .95])
    if drop_extrema:
        filtered_df: df.DataFrame = df.copy()
        for (txp, txp_df) in df.groupby("txp"):
            filtered_df.drop(labels=txp_df.loc[txp_df['cfo'] < description.loc[txp, ('cfo', '5%')]].index,
                             inplace=True, errors='ignore')
            filtered_df.drop(labels=txp_df.loc[txp_df['cfo'] > description.loc[txp, ('cfo', '95%')]].index,
                             inplace=True, errors='ignore')
            filtered_df.drop(labels=txp_df.loc[txp_df['snr'] == np.nan].index,
                             inplace=True, errors='ignore')
            filtered_df.drop(labels=txp_df.loc[txp_df['snr'] < description.loc[txp, ('snr', '5%')]].index,
                             inplace=True, errors='ignore')
    ax.plot(description.loc[:, ('snr', '50%')],
            description.loc[:, ('ber', 'mean')], "-s", label='Measurements')
    if drop_extrema:
        description = filtered_df.groupby("txp").describe(percentiles=[.5])
        ax.plot(description.loc[:, ('snr', '50%')],
                description.loc[:, ('ber', 'mean')], "-s", label='Without extreme CFO and SNR')
    if drop_last_bytes:
        ax.plot(description.loc[:, ('snr', '50%')],
                description.loc[:, ('ber_first_bytes', 'mean')], "-s", label='Only first bytes of each packet')
    ax.set_xlabel('SNR estimation [dB]')
    ax.set_ylabel('BER')
    ax.set_ylim((2e-6, 1))
    ax.set_xlim((5.0, 30.0))
    ax.legend(loc=3)
    fig.suptitle('BER vs SNR estimation')
    return fig


def plot_PER_vs_SNRest(
    df: pd.DataFrame, drop_extrema: bool = True,
    comp_sim: bool = False, SNR_sim: np.ndarray[float] = None,
    PER_sim: list[np.ndarray[float]] = None, labels_sim: list[str] = None
) -> mpl.figure.Figure:

    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title('Measurements: PER vs SNR est')
    if comp_sim:
        for PER, label in zip(PER_sim, labels_sim):
            BER_SNR_sim(SNR_sim, PER, label, fig)
    ax.set_yscale('log')
    description = df.groupby("txp").describe(percentiles=[.05, .5, .95])
    if drop_extrema:
        filtered_df: df.DataFrame = df.copy()
        for (txp, txp_df) in df.groupby("txp"):
            filtered_df.drop(labels=txp_df.loc[txp_df['cfo'] < description.loc[txp, ('cfo', '5%')]].index,
                             inplace=True, errors='ignore')
            filtered_df.drop(labels=txp_df.loc[txp_df['cfo'] > description.loc[txp, ('cfo', '95%')]].index,
                             inplace=True, errors='ignore')
            filtered_df.drop(labels=txp_df.loc[txp_df['snr'] == np.nan].index,
                             inplace=True, errors='ignore')
            filtered_df.drop(labels=txp_df.loc[txp_df['snr'] < description.loc[txp, ('snr', '5%')]].index,
                             inplace=True, errors='ignore')
    ax.plot(description.loc[:, ('snr', '50%')],
            1-description.loc[:, ('correct', 'mean')].array, "-s", label='Measurements')
    if drop_extrema:
        description = filtered_df.groupby("txp").describe(percentiles=[.5])
        ax.plot(description.loc[:, ('snr', '50%')],
                1-description.loc[:, ('correct', 'mean')].array, "-s", label='Without extreme CFO and SNR')
    ax.set_xlabel('SNR estimation [dB]')
    ax.set_ylabel('PER')
    ax.set_ylim((2e-6, 1))
    ax.set_xlim((5.0, 30.0))
    ax.legend(loc=3)
    fig.suptitle('PER vs SNR estimation')
    return fig


def plot_detection_rate(
    df: pd.DataFrame, npackets: int = 50,
    comp_sim: bool = False, SNR_sim: np.ndarray[float] = None,
    preamble_mis: np.ndarray[float] = None, preamble_false: np.ndarray[float] = None
) -> mpl.figure.Figure:

    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title('Measurements: Detection rate')
    if comp_sim:
        detection_sim(SNR_sim, preamble_mis, preamble_false, fig)

    description = df.groupby("txp").describe()

    ax.plot(description.loc[:, ('snr', '50%')],
            description.loc[:, ('snr', 'count')] / npackets * 100, "-s",
            color="black", label="Measure: Transmitted/Received packets ratio")
    ax.set_xlabel('SNR estimation [dB]')
    ax.set_ylabel('[%]')
    ax.legend(loc=6, fontsize='small')
    fig.suptitle('Packet detection metrics vs SNR estimation')

    if comp_sim:
        plt.savefig('R6_Graphs/20-12_N=16/detection_rate_with_sim.png', dpi=300)
    else:
        plt.savefig('R6_Graphs/20-12_N=16/detection_rate.png', dpi=300)

    return fig


def BER_SNR_sim(
    SNR: np.ndarray[float], BER: np.ndarray[float], label: str, fig: mpl.figure.Figure
) -> mpl.figure.Figure:

    ax = fig.gca()
    ax.plot(SNR, BER, "-s", label=label)
    ax.grid(True)

    return fig


def detection_sim(
    SNR: np.ndarray[float], preamble_mis: np.ndarray[float], preamble_false: np.ndarray[float],
    fig: mpl.figure.Figure
) -> mpl.figure.Figure:

    ax = fig.gca()
    ax.plot(SNR, preamble_mis * 100, "-s",
            label="Simulation: Miss-detection")
    ax.plot(SNR, preamble_false * 100, "-s",
            label="Simulation: False-detection")
    return fig


def plot_SNRest_vs_dist(
    df: pd.DataFrame, title: str = '', fig: mpl.figure.Figure = None
) -> mpl.figure.Figure:

    groups = df.groupby('distance')
    snr = []
    for idxs in groups.groups.values():
        ls = list(df.loc[idxs, 'snr'].array)
        snr.append(ls)

    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title('Measurements: SNR est vs Distance')
    ax.boxplot(snr, showfliers=False, positions=list(groups.groups.keys()))
    ax.set_xlabel('Distance [m]')
    ax.set_ylabel('$SNR_{est}$ [dB]')
    ax.set_title(title)
    ax._children[-1].set_label(title)
    ax.legend()
    fig.suptitle('SNR evolution over the distance')
    return fig


def main() -> None:
    num_bytes: int = 200
    npackets: int = 200
    # __________Simulation without bypasses__________
    sim.main(['--FIR', '--no_show', '-p', '1600', '-n', '50000', '-m', '16', '-r', '1500'])
    SNRs_est = sim.get_SNRs_est()
    BER = sim.get_BER()
    PER = sim.get_PER()
    preamble_mis = sim.get_preamble_mis()
    preamble_false = sim.get_preamble_false()
    # __________Simulation with all bypasses__________
    sim.main(['--no_show', '-p', '1600', '-n', '50000', '-m', '16', '-r', '1500', '-d', '-c', '-s'])
    BER_bypass_all = sim.BER
    PER_bypass_all = sim.PER
    # __________Read measurements data__________
    # Use custom function 'read_measurements' (see above) to retrieve data and metadata
    # IMPORTANT: use the filepath relative to THIS file's directory (LELEC210X_GROUP_E/telecom/)
    # Don't hesitate to add custom plot functions and try to keep a similar signature for compatibility issues
    curdir = os.path.dirname(__file__)+'/'
    df, payload_df = read_measurements(
        './hands_on_measurements/measurements/20-12_measurements.txt',
        './hands_on_measurements/measurements/20-12_compl_measurements.txt',
        num_bytes=num_bytes, first_bytes=100,
        txp=True, ber=True, distance=False)
    plt.close('all')
    fig = plot_BER_vs_SNRest(df, comp_sim=True, SNR_sim=SNRs_est, BER_sim=[BER, BER_bypass_all],
                             labels_sim=['Simulation', 'Bypass all synchronization'])
    fig.savefig(curdir+'R6_Graphs/BER vs SNR measurements and simulation.svg')
    fig = plot_PER_vs_SNRest(df, comp_sim=True, drop_extrema=False,
                             SNR_sim=SNRs_est, PER_sim=[PER, PER_bypass_all],
                             labels_sim=['Simulation', 'Bypass all synchronization'])
    fig.savefig(curdir+'R6_Graphs/PER vs SNR measurements and simulation.svg')
    fig = plot_detection_rate(df, npackets=npackets, comp_sim=True, SNR_sim=SNRs_est,
                              preamble_mis=preamble_mis, preamble_false=preamble_false)
    fig.savefig(curdir+'R6_Graphs/Detection metrics.svg')
    fig = plot_BER_vs_byte_pos(payload_df)
    fig.savefig(curdir+'R6_Graphs/BER vs byte position.svg')
    df, payload_df = read_measurements(
        './hands_on_measurements/measurements/20-12_measurements_N=16.txt',
        './hands_on_measurements/measurements/20-12_compl_measurements_N=16.txt',
        num_bytes=num_bytes, txp=True, ber=False, distance=False)
    fig = plot_cfo_hist(df, N=16, color='C0')
    fig.savefig(curdir+'R6_Graphs/CFO histogram N = 16.svg')
    fig = plot_SNRest_vs_CFOest(df, N=16)
    fig.savefig(curdir+'R6_Graphs/SNR vs CFO N=16.svg')
    df, payload_df = read_measurements(
        './hands_on_measurements/measurements/20-12_measurements_N=8.txt',
        './hands_on_measurements/measurements/20-12_compl_measurements_N=8.txt',
        num_bytes=num_bytes, txp=True, ber=False, distance=False)
    fig = plot_cfo_hist(df, N=8, color='C1')
    fig.savefig(curdir+'R6_Graphs/CFO histogram N = 8.svg')
    fig = plot_SNRest_vs_CFOest(df, N=8)
    fig.savefig(curdir+'R6_Graphs/SNR vs CFO N=8.svg')
    df, payload_df = read_measurements(
        './hands_on_measurements/measurements/20-12_measurements_N=4.txt',
        './hands_on_measurements/measurements/20-12_compl_measurements_N=4.txt',
        num_bytes=num_bytes, txp=True, ber=False, distance=False)
    fig = plot_cfo_hist(df, N=4, color='C2')
    fig.savefig(curdir+'R6_Graphs/CFO histogram N = 4.svg')
    fig = plot_SNRest_vs_CFOest(df, N=4)
    fig.savefig(curdir+'R6_Graphs/SNR vs CFO N=4.svg')
    df, payload_df = read_measurements(
        './hands_on_measurements/measurements/20-12_measurements distance.txt',
        './hands_on_measurements/measurements/20-12_compl_measurements distance.txt',
        num_bytes=num_bytes, txp=False, ber=False, distance=True)
    fig = plot_SNRest_vs_dist(df, title='Closed room')
    fig.savefig(curdir+'R6_Graphs/SNR vs distance.svg')
    df, payload_df = read_measurements(
        './hands_on_measurements/measurements/22-12_measurements distance.txt',
        './hands_on_measurements/measurements/22-12_compl_measurements distance.txt',
        num_bytes=num_bytes, txp=False, ber=False, distance=True)
    fig = plot_SNRest_vs_dist(df, title='Tennis field')
    fig.savefig(curdir+'R6_Graphs/SNR vs distance tennis field.svg')
    # __________Show plots__________
    plt.show()


if __name__ == '__main__':
    main()
