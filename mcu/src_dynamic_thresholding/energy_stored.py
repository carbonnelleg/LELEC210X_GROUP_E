import numpy as np
import matplotlib.pyplot as plt

# Constants
v_base = 3.6  # Baseline voltage
v_max = 4.5   # Maximum voltage

# Function to calculate energy stored in the capacitor for a given voltage range
def calculate_energy(cap_uF, v_base, v_max):
    C = cap_uF / 1_000_000  # Convert µF to Farads
    voltages = np.linspace(v_base, v_max, 100)  # Voltage range from 3.6V to 4.5V
    energies = 0.5 * C * voltages**2  # Energy stored in the capacitor: E = 0.5 * C * V^2
    
    # Calculate energy difference from the energy at 3.6V (baseline)
    energy_at_base = 0.5 * C * v_base**2  # Energy at baseline voltage (3.6V)
    energies_above_base = energies - energy_at_base  # Subtract baseline energy
    
    return voltages, energies_above_base * 1000  # Return energies in mJ

# Capacitor values to compare (1mF, 2.2mF, 3.2mF)
capacitors = [1000]  # in microfarads (µF) , 2200, 3200

# Plotting
plt.figure(figsize=(10, 6))

# Loop through capacitors and plot their results
for cap_uF in capacitors:
    voltages, energies = calculate_energy(cap_uF, v_base, v_max)
    plt.plot(voltages, energies, label=f'{cap_uF / 1000} mF')

plt.title("Energy Stored Above 3.6V vs Voltage (between 3.6V and 4.5V)")
plt.xlabel("Voltage [V]")
plt.ylabel("Energy Stored Above 3.6V [mJ]")
plt.legend(title="Capacitance")
plt.grid(True)
plt.tight_layout()
plt.show()
