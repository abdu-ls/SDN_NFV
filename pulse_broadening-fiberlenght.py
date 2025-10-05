# Creating plots for "Chromatic Dispersion Visualization"
# - Pulse broadening (FWHM) vs fiber length for several spectral widths
# - Eye diagrams (no dispersion, moderate, high dispersion)
#
# Notes:
# - Units: time in picoseconds (ps), wavelength width in nm, D in ps/(nm·km)
# - Uses simple approximation: dispersion-induced broadening (ps) ≈ D * Δλ * L
# - Output FWHM = sqrt(τ0^2 + (D*Δλ*L)^2)
# - Eye diagrams: binary NRZ stream generated as impulses at symbol centers convolved
#   with Gaussian pulse (FWHM = output FWHM); plotted over two symbol periods per trace.
#
import numpy as np
import matplotlib.pyplot as plt

# Parameters
D = 17.0  # ps / (nm·km) typical for standard single-mode fiber at 1550 nm
tau0 = 10.0  # initial pulse FWHM in ps (transmitter pulse width)
lengths_km = np.linspace(0, 200, 201)  # 0 to 200 km
delta_lams = [0.1, 1.0, 10.0]  # spectral widths in nm (narrow laser, broader, very broad)

# Function to convert FWHM to gaussian sigma (ps)
def fwhm_to_sigma(fwhm_ps):
    return fwhm_ps / (2 * np.sqrt(2 * np.log(2)))

def sigma_to_fwhm(sigma_ps):
    return sigma_ps * 2 * np.sqrt(2 * np.log(2))

# Compute broadening curves
broadening = {}
for dl in delta_lams:
    disp_broad_ps = D * dl * lengths_km  # simple approx
    out_fwhm = np.sqrt(tau0**2 + disp_broad_ps**2)
    broadening[dl] = out_fwhm

# Plot 1: Pulse FWHM vs Fiber Length
plt.figure(figsize=(8,4))
for dl in delta_lams:
    plt.plot(lengths_km, broadening[dl], label=f"Δλ = {dl} nm")
plt.xlabel("Fiber length (km)")
plt.ylabel("Pulse FWHM (ps)")
plt.title("Pulse Broadening vs Fiber Length (D = 17 ps/(nm·km), τ₀ = 10 ps)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# Prepare an NRZ bitstream and function to create eye diagram for a given length
Rb = 10e9  # bit rate 10 Gbps
Ts_ps = 1e12 / Rb  # symbol period in ps (100 ps)
Ts = Ts_ps  # keep in ps
dt = Ts / 200.0  # time resolution ~200 samples per symbol (in ps)
dt = max(dt, 0.5)  # ensure not too small for performance; min 0.5ps
fs = 1.0 / dt

def generate_eye_diagram(length_km, delta_lambda_nm, num_bits=200, snr_db=40):
    # compute output FWHM and sigma in ps
    disp_broad = D * delta_lambda_nm * length_km
    fwhm_out = np.sqrt(tau0**2 + disp_broad**2)
    sigma_out = fwhm_to_sigma(fwhm_out)
    # time axis for the whole signal
    T_total = num_bits * Ts
    t = np.arange(0, T_total, dt)  # in ps
    # create bit sequence (random)
    np.random.seed(1)
    bits = np.random.randint(0, 2, size=num_bits)
    # create impulse train at bit centers
    signal_imp = np.zeros_like(t)
    bit_centers = (np.arange(num_bits) + 0.5) * Ts
    idx_centers = (bit_centers / dt).astype(int)
    # place impulses scaled by bit value
    for i, b in enumerate(bits):
        signal_imp[idx_centers[i]] = b
    # gaussian kernel (in ps)
    t_kernel = np.arange(-5*Ts, 5*Ts, dt)  # kernel over ±5 symbol periods
    kernel = np.exp(-0.5 * (t_kernel / sigma_out)**2)
    kernel = kernel / (np.sum(kernel) * (dt))  # normalize area
    # convolve (use np.convolve; account for dt scaling already done via normalization)
    sig = np.convolve(signal_imp, kernel, mode='same') * (1.0)  # amplitude in arb units
    # add small AWGN for realism
    snr_linear = 10**(snr_db/10.0)
    signal_power = np.mean(sig**2)
    noise_power = signal_power / snr_linear if signal_power>0 else 0
    noise = np.sqrt(noise_power) * np.random.randn(len(sig))
    sig_noisy = sig + noise
    return t, sig_noisy, bits, fwhm_out

# Choose three fiber lengths to illustrate eye impact: 0 km (no dispersion), 50 km (moderate), 200 km (high)
cases = [0, 50, 200]
delta_lambda_example = 1.0  # 1 nm spectral width example (common broad laser/LED-ish source)

for L in cases:
    t, sig, bits, fwhm_out = generate_eye_diagram(L, delta_lambda_example, num_bits=400, snr_db=60)
    # Build eye diagram: overlay two symbol periods worth of samples aligned to symbol boundaries
    samples_per_symbol = int(np.round(Ts / dt))
    # Extract central portion to avoid convolution edge effects
    start_idx = samples_per_symbol * 50
    end_idx = start_idx + samples_per_symbol * 200
    sig_seg = sig[start_idx:end_idx]
    n_symbols = int(len(sig_seg) / samples_per_symbol)
    # reshape into symbols
    frames = sig_seg[:n_symbols * samples_per_symbol].reshape((n_symbols, samples_per_symbol))
    # time axis for one symbol (ps)
    t_symbol = np.linspace(0, Ts, samples_per_symbol, endpoint=False)
    plt.figure(figsize=(6,3.5))
    for row in frames[:200]:  # overlay up to 200 traces for clarity
        plt.plot(t_symbol, row, linewidth=0.5)
    plt.title(f"Eye Diagram - L = {L} km, Δλ = {delta_lambda_example} nm, Output FWHM ≈ {fwhm_out:.1f} ps")
    plt.xlabel("Time (ps)")
    plt.ylabel("Amplitude (arb. units)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

