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

# Function to convert energy to CAPA_LVL
def energy_to_capa_lvl(energy_mJ_array, cap_uF=1000, v_base=3.6, adc_step_v=0.075, adc_min=48, adc_range=12):
    C = cap_uF / 1_000_000  # convert µF to F
    E_base = 0.5 * C * v_base**2  # energy at baseline voltage in J
    energy_J_array = np.array(energy_mJ_array) / 1000  # convert mJ to J

    V_target_squared = (2 * energy_J_array) / C + v_base**2
    V_target = np.sqrt(V_target_squared)

    adc_values = (V_target - v_base) / adc_step_v + adc_min
    capa_lvl = (adc_values - adc_min) / adc_range

    return capa_lvl

cap_ufs = [1000]  # in microfarads (µF) , 2200, 3200
cap_uF = cap_ufs[0]  # Use the first capacitor value for plotting

# Now, let's add the threshold graph (CAPA_LVL vs Voltage)
voltages = np.linspace(v_base, v_max, 100)
energies = 0.5 * (cap_uF / 1_000_000) * voltages**2  # Energy stored for the voltage range
energies_above_base = energies - 0.5 * (cap_uF / 1_000_000) * v_base**2  # Energy above 3.6V

# Convert energy to CAPA_LVL for the threshold graph
capa_levels = energy_to_capa_lvl(energies_above_base * 1000)  # Convert energy to CAPA_LVL

# Plot the Threshold vs Voltage graph
plt.figure(figsize=(10, 6))
plt.plot(voltages, capa_levels, label="Threshold (CAPA_LVL) vs Voltage", color='green')
plt.axhline(1.0, color='gray', linestyle='--', label='CAPA_LVL = 1.0')  # Reference line for CAPA_LVL = 1
plt.title("Threshold (CAPA_LVL) vs Voltage")
plt.xlabel("Voltage [V]")
plt.ylabel("CAPA_LVL (Threshold)")
plt.grid(True)
plt.legend()
plt.tight_layout()

# Add more ticks to both axes
plt.xticks(np.arange(v_base, v_max + 0.1, 0.1))
plt.yticks(np.arange(0, 1.1, 0.1))

plt.show()
