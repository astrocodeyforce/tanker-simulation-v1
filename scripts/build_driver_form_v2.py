#!/usr/bin/env python3
"""
Minimal 1-page Driver Unloading Data Sheet (V2) — clean layout.
Only fields that CANNOT be obtained from Bill of Lading or truck records.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os

pdf_path = '/work/data/parametric_sweeps/Driver_Unloading_Sheet_V2.pdf'

fig, ax = plt.subplots(figsize=(8.5, 11))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis('off')

# --- Drawing helpers ---
LEFT = 0.06
RIGHT = 0.94

def put(x, yy, txt, size=10, bold=False, color='black', ha='left'):
    ax.text(x, yy, txt, fontsize=size,
            fontweight='bold' if bold else 'normal',
            color=color, va='top', ha=ha, transform=ax.transAxes)

def uline(x1, x2, yy):
    """Underline / fill-in blank."""
    ax.plot([x1, x2], [yy, yy], 'k-', lw=0.5, transform=ax.transAxes)

def hline(yy, lw=0.8):
    """Full-width horizontal rule."""
    ax.plot([LEFT, RIGHT], [yy, yy], 'k-', lw=lw, transform=ax.transAxes)

def cbox(label, x, yy):
    """Checkbox with label."""
    sz = 0.013
    rect = plt.Rectangle((x, yy - 0.016), sz, sz,
                          fill=False, edgecolor='black', lw=0.7,
                          transform=ax.transAxes)
    ax.add_patch(rect)
    put(x + 0.022, yy, label, size=10)

# ============================================================
y = 0.96

# TITLE
put(0.50, y, 'DRIVER UNLOADING DATA SHEET', size=17, bold=True, ha='center')
y -= 0.032
put(0.50, y, 'Quick version \u2014 fill out during each delivery', size=9,
    color='#555555', ha='center')
y -= 0.030
hline(y, lw=1.2)
y -= 0.025

# ─────────────────── 1. DELIVERY INFO ───────────────────
put(LEFT, y, '1.  DELIVERY INFO', size=12, bold=True)
y -= 0.040

put(LEFT, y, 'Date:', size=10)
uline(0.14, 0.42, y - 0.020)
put(0.48, y, 'Driver Name:', size=10)
uline(0.63, RIGHT, y - 0.020)
y -= 0.050

put(LEFT, y, 'Customer / Site:', size=10)
uline(0.24, 0.56, y - 0.020)
put(0.60, y, 'BOL #:', size=10)
uline(0.70, RIGHT, y - 0.020)
y -= 0.045
hline(y, lw=0.4)
y -= 0.025

# ─────────────────── 2. UNLOADING TIME ───────────────────
put(LEFT, y, '2.  UNLOADING TIME', size=12, bold=True)
put(0.34, y, '\u2190 most important!', size=9, color='#CC0000')
y -= 0.040

put(LEFT, y, 'Start Time:', size=10)
uline(0.20, 0.36, y - 0.020)
put(0.40, y, 'End Time:', size=10)
uline(0.53, 0.68, y - 0.020)
put(0.72, y, 'Total (min):', size=10)
uline(0.85, RIGHT, y - 0.020)
y -= 0.050

put(LEFT, y, 'Any stops during unloading?', size=10)
cbox('No', 0.36, y)
cbox('Yes \u2192 how long?', 0.46, y)
uline(0.72, RIGHT, y - 0.020)
y -= 0.045
hline(y, lw=0.4)
y -= 0.025

# ─────────────────── 3. AIR COMPRESSOR ───────────────────
put(LEFT, y, '3.  AIR COMPRESSOR', size=12, bold=True)
y -= 0.040

put(LEFT, y, 'Compressor SCFM rating:', size=10)
uline(0.32, 0.46, y - 0.020)
put(0.47, y, 'SCFM', size=10)
put(0.56, y, '(check nameplate on compressor)', size=9, color='#777777')
y -= 0.050

put(LEFT, y, 'If unknown, compressor make / model:', size=10)
uline(0.42, RIGHT, y - 0.020)
y -= 0.045
hline(y, lw=0.4)
y -= 0.025

# ─────────────────── 4. HOSE SETUP ───────────────────
put(LEFT, y, '4.  HOSE SETUP AT SITE', size=12, bold=True)
y -= 0.040

put(LEFT, y, 'Total hose length used:', size=10)
uline(0.31, 0.44, y - 0.020)
put(0.45, y, 'ft', size=10)
put(0.52, y, '(estimate is fine)', size=9, color='#777777')
y -= 0.050

put(LEFT, y, 'Receiver tank vs truck:', size=10)
cbox('Same level', 0.31, y)
cbox('Higher (uphill)', 0.50, y)
cbox('Lower', 0.74, y)
y -= 0.050

put(LEFT, y, 'If higher, roughly how many feet up?', size=10)
uline(0.44, 0.56, y - 0.020)
put(0.57, y, 'ft', size=10)
put(0.64, y, '(5? 10? 20? just guess)', size=9, color='#777777')
y -= 0.045
hline(y, lw=0.4)
y -= 0.025

# ─────────────────── 5. HOW DID IT GO ───────────────────
put(LEFT, y, '5.  HOW DID IT GO?', size=12, bold=True)
y -= 0.040

put(LEFT, y, 'Flow speed:', size=10)
cbox('Normal', 0.22, y)
cbox('Slower than usual', 0.40, y)
cbox('Very slow', 0.66, y)
y -= 0.050

put(LEFT, y, 'Any problems?', size=10)
cbox('None', 0.22, y)
cbox('Line clog', 0.36, y)
cbox('Pressure issue', 0.54, y)
cbox('Leak', 0.74, y)
y -= 0.050

put(LEFT, y, 'Notes:', size=10)
uline(0.14, RIGHT, y - 0.020)
y -= 0.038
uline(LEFT, RIGHT, y - 0.020)
y -= 0.045
hline(y, lw=0.4)
y -= 0.025

# ─────────────────── 6. GAUGE READINGS ───────────────────
put(LEFT, y, '6.  GAUGE READINGS', size=12, bold=True)
put(0.34, y, '(only if easy to see)', size=9, color='#777777')
y -= 0.040

put(LEFT, y, 'Tank pressure at start:', size=10)
uline(0.31, 0.44, y - 0.020)
put(0.45, y, 'psi', size=10)

put(0.54, y, 'Max pressure seen:', size=10)
uline(0.76, 0.88, y - 0.020)
put(0.89, y, 'psi', size=10)
y -= 0.050

# ============================================================
# FOOTER — well below content
# ============================================================
hline(0.045, lw=0.8)
put(LEFT, 0.028, "That's it! Thank you. Drop in the cab folder or snap a photo.",
    size=9, color='#888888')
put(RIGHT, 0.028, 'V2', size=8, color='#aaaaaa', ha='right')

# ---- Save ----
plt.subplots_adjust(left=0.02, right=0.98, top=0.99, bottom=0.01)
os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
with PdfPages(pdf_path) as pdf:
    pdf.savefig(fig, dpi=150)
plt.close()

sz = os.path.getsize(pdf_path)
print(f"PDF saved: {pdf_path}  ({sz:,} bytes, 1 page)")
