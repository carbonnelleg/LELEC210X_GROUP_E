import numpy as np
import matplotlib.pyplot as plt

def energy_to_capa_lvl(energy_mJ_array, cap_uF=1000, v_base=3.6, adc_step_v=0.075, adc_min=48, adc_range=12):
    C = cap_uF / 1_000_000  # convert µF to F
    E_base = 0.5 * C * v_base**2  # energy at baseline voltage in J
    energy_J_array = np.array(energy_mJ_array) / 1000  # convert mJ to J

    V_target_squared = (2 * energy_J_array) / C + v_base**2
    V_target = np.sqrt(V_target_squared)

    adc_values = (V_target - v_base) / adc_step_v + adc_min
    capa_lvl = (adc_values - adc_min) / adc_range

    return capa_lvl

# Generate energy levels from 0 to 4 mJ above 3.6V
energy_levels_mJ = np.linspace(0, 4.0, 100)
capa_levels = energy_to_capa_lvl(energy_levels_mJ)

# Plot
plt.figure(figsize=(8, 5))
plt.plot(energy_levels_mJ, capa_levels, label="CAPA_LVL vs Energy", color='blue')
plt.axhline(1.0, color='gray', linestyle='--', label='CAPA_LVL = 1.0')
plt.title("CAPA_LVL Threshold vs Extra Energy Stored (above 3.6V)")
plt.xlabel("Energy above 3.6V [mJ]")
plt.ylabel("CAPA_LVL")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()
