#!/usr/bin/env python3
"""Generate a 2-page Driver Unloading Data Collection Form as PDF."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os

pdf_path = '/work/data/parametric_sweeps/Driver_Unloading_Data_Form.pdf'

class FormBuilder:
    def __init__(self, ax):
        self.ax = ax
        self.y = 0.97

    def title(self, t, sz=14):
        self.ax.text(0.05, self.y, t, transform=self.ax.transAxes, fontsize=sz,
                     fontweight='bold', va='top')
        self.y -= 0.028

    def line(self, t, sz=9):
        self.ax.text(0.05, self.y, t, transform=self.ax.transAxes, fontsize=sz, va='top')
        self.y -= 0.022

    def blank(self):
        self.y -= 0.012

    def field(self, label):
        self.ax.text(0.05, self.y, label + ':  ______________________________',
                     transform=self.ax.transAxes, fontsize=9, va='top')
        self.y -= 0.027

    def separator(self):
        self.ax.plot([0.05, 0.95], [self.y + 0.01, self.y + 0.01],
                     transform=self.ax.transAxes, color='black', lw=0.5)
        self.blank()


with PdfPages(pdf_path) as pdf:
    # ── PAGE 1 ──
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis('off')
    f = FormBuilder(ax)

    f.title('TANKER UNLOADING DATA COLLECTION FORM', 16)
    f.line('Fill out after each delivery (~2 min). Return to dispatch.', 9)
    f.blank()
    f.separator()

    f.title('DRIVER INFO', 11)
    f.field('Driver Name')
    f.field('Date')
    f.field('Delivery Location')
    f.blank()

    f.title('1. TANKER INFO', 11)
    f.field('Tanker ID / Truck #')
    f.field('Tank capacity (gallons)')
    f.field('Tank shape (Horizontal Cylinder / Oval / Other)')
    f.field('Approximate tank diameter (inches)')
    f.field('Approximate tank length (feet)')
    f.field('Internal baffles? (Yes / No / Not Sure)')
    f.field('How many baffles?')
    f.blank()

    f.title('2. THE LOAD', 11)
    f.field('Product / Chemical name')
    f.field('Thickness (Water-thin / Paint-like / Thick paste / Very thick)')
    f.field('How full was the tank? (gallons)')
    f.field('Was the tank completely emptied? (Yes / No)')
    f.field('If no, how much was left? (gallons)')
    f.blank()

    f.title('3. AIR COMPRESSOR', 11)
    f.field('Compressor type / brand')
    f.field('Compressor rating (SCFM) if known')
    f.field('Pre-pressurize before opening valve? (Yes / No)')
    f.field('If yes, to what pressure (psig)?')
    f.field('How long did pre-pressurizing take? (min)')
    f.field('Max pressure gauge reading during unload (psig)')
    f.blank()

    f.title('4. VALVE & PIPING', 11)
    f.field('Discharge valve location (Belly center / Rear / Side / Other)')
    f.field('Valve size (2" / 3" / 4" / Other)')
    f.field('How many hoses used? (1 / 2 / Other)')
    f.field('Hose diameter (2" / 3" / 4" / Other)')
    f.field('Hose length - truck to customer (feet)')
    f.field('Extra fittings? (elbows, reducers, Y-splits)')
    f.field('If yes, describe')

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close()

    # ── PAGE 2 ──
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis('off')
    f = FormBuilder(ax)

    f.title('5. CUSTOMER SITE', 11)
    f.field('Is the receiving tank pressurized? (Yes / No)')
    f.field('If yes, what pressure (psig)?')
    f.field('Receiving tank vs truck? (Higher / Same / Lower)')
    f.field('If higher, approximately how much? (feet)')
    f.field('Incline/slope where parked? (Flat / Slight / Steep)')
    f.field('Slope direction? (Toward rear / Toward front / Flat)')
    f.blank()

    f.title('6. TIMING  (MOST IMPORTANT!)', 12)
    f.line('Use phone stopwatch or note the clock time:', 9)
    f.blank()
    f.field('Started compressor (air on)')
    f.field('Opened discharge valve (flow starts)')
    f.field('Flow visibly slowed down')
    f.field('Flow stopped / valve closed')
    f.field('Compressor turned off')
    f.blank()
    f.line('OR if you cannot track individual times:', 9)
    f.field('Total time valve open to valve close (min)')
    f.field('Total time compressor was running (min)')
    f.blank()

    f.title('7. ANYTHING UNUSUAL?', 11)
    for item in ['Flow stopped and restarted', 'Had to increase/decrease pressure',
                 'Hose kinked or blocked', 'Product unusually thick or thin',
                 'Very hot or cold weather']:
        f.line('[  ]  ' + item, 9)
    f.field('Other notes')
    f.blank()

    f.title('8. OPTIONAL - GAUGE READINGS', 11)
    f.line('Jot down pressure gauge every 10 minutes:', 9)
    f.blank()
    ax.text(0.05, f.y, 'Time (min)       Pressure (psig)       Flow going?',
            transform=ax.transAxes, fontsize=9, va='top', fontweight='bold')
    f.y -= 0.022
    for t in ['0 (start)', '10', '20', '30', '40', '50', 'Done']:
        ax.text(0.05, f.y, f'{t:12s}       ____________          ____________',
                transform=ax.transAxes, fontsize=9, va='top', family='monospace')
        f.y -= 0.022
    f.blank()
    f.blank()
    f.separator()
    f.line('Thank you! This data helps us optimize unloading times.', 10)

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close()

size = os.path.getsize(pdf_path)
print(f'PDF created: {pdf_path} ({size:,} bytes)')
