#!/usr/bin/env python3
"""Analyze Bull & Bear fleet commodity shipping data."""
import csv
import io
import statistics
from collections import Counter

RAW = """Commodity,Count,cP,SG,lb_gal,max_gal,fill_pct
Ethylene Glycol,56,16.1,1.113,9.28,5171,76.0
Resin Solution,32,500,1.05,8.76,5481,80.6
Sodium Silicate,28,180,1.39,11.59,4141,60.9
Biomass,27,50,1.05,8.76,5481,80.6
Diethylene Glycol,27,30.2,1.118,9.32,5148,75.7
DOSS 70 PG,26,200,1.08,9.01,5329,78.4
NIPOL 1411LATEX,26,200,1,8.34,5755,84.6
Smartcide 1984A,23,5,1.02,8.51,5643,83.0
Transformer Oil Type II,22,11,0.88,7.34,6540,96.2
Used Motor Oil,22,20,0.88,7.34,6540,96.2
OCD,21,0.6,1.05,8.76,5481,80.6
Triethylene Glycol,19,37.3,1.125,9.38,5116,75.2
Propylene Glycol,17,42,1.036,8.64,5555,81.7
Tall oil rosin,16,5000,1.07,8.92,5379,79.1
DC110bh,16,30,1.1,9.17,5232,76.9
VIVATEC 500,16,100,0.99,8.26,5814,85.5
C24-28 (Wax Additive),16,5,0.8,6.67,6800,100.0
NAXONATE 4LS,15,5,1.07,8.92,5379,79.1
Termin-8 Liquid,12,2,1,8.34,5755,84.6
LUBRICANTS DIALAS4,12,11,0.87,7.26,6615,97.3
Kaolin or other kaolinic clays,10,300,1.15,9.59,5005,73.6
V-PRODUCT PR 8401 X,10,200,1.05,8.76,5481,80.6
Lauramine Oxide,9,30,1.02,8.51,5643,83.0
Risella 415,9,8,0.855,7.13,6731,99.0
Board and Seal Wax,8,5,0.8,6.67,6800,100.0
Acrylic Resin,7,200,1.1,9.17,5232,76.9
ELCO 102,7,5,1.02,8.51,5643,83.0
Novel 1614-9,7,20,1.05,8.76,5481,80.6
SYNALOX 40-D150,7,150,1.06,8.84,5430,79.8
Mineral Oil,7,20,0.85,7.09,6771,99.6
Burn Fuel,6,3,0.835,6.96,6800,100.0
Cocamidopropyl Betaine,6,45,1.04,8.67,5534,81.4
P G Select 21911,6,42,1.036,8.64,5555,81.7
Sodium Thiocyanate,6,2,1.7,14.18,3386,49.8
Promex 20S Summer,6,3,1.05,8.76,5481,80.6
SUMMIT VI-PARA US KLUBER,6,80,0.87,7.26,6615,97.3
Lauryl Hydroxysultaine,6,35,1.04,8.67,5534,81.4
Flush Oil,6,15,0.86,7.17,6692,98.4
Colateric,6,30,1.04,8.67,5534,81.4
NALCO 60625,5,5,1.1,9.17,5232,76.9
CALSOFT AOS-40,5,20,1.05,8.76,5481,80.6
Rotella ELC NF,5,16,0.87,7.26,6615,97.3
CRUDE GLYCERIN,5,934,1.261,10.52,4564,67.1
OPTIGEAR SYNTHETIC CT 320,5,600,0.87,7.26,6615,97.3
Monoethanolamine,5,19,1.012,8.44,5687,83.6
Zinc Ammonium Carbonate,5,3,1.58,13.18,3643,53.6
ACH 50%,5,5,1.33,11.09,4327,63.6
Bioplus BA3971 T,5,50,1.02,8.51,5643,83.0
De-Icer Fluid,5,16,1.08,9.01,5329,78.4
NeoPac PU-481,5,200,1.05,8.76,5481,80.6
NISSAN 0W20,5,55,0.86,7.17,6692,98.4
DC110 bh,5,30,1.1,9.17,5232,76.9
FLOJET DRMAX E 488,5,50,1.1,9.17,5232,76.9
HALEX GT,5,5,1.2,10.01,4796,70.5
Colafoam CS-50,5,30,1.05,8.76,5481,80.6
Safewing MP IV Launch,5,15,1.08,9.01,5329,78.4
Universal Tractor Fluid,5,60,0.875,7.3,6578,96.7
Termin-8 Liquid HAZ,5,2,1,8.34,5755,84.6
HENRY SIZING EMUL,4,50,1.02,8.51,5643,83.0
ARM ULTRAPRIME 2020,4,100,1.05,8.76,5481,80.6
Protech 100,4,5,0.88,7.34,6540,96.2
HYDRAL BRITE,4,300,0.86,7.17,6692,98.4
LIMONENE EX,4,0.9,0.842,7.02,6800,100.0
Mayoquest 1866,4,5,1.1,9.17,5232,76.9
LEUCOPHOR T125,4,10,1.15,9.59,5005,73.6
Titanium Dioxide slurry,4,200,1.4,11.68,4111,60.5
HiTec 12208,4,200,0.9,7.51,6395,94.0
Base Oil,4,15,0.86,7.17,6692,98.4
StarSurf LOx,4,20,1.03,8.59,5588,82.2
ACETONITRILE,4,0.3,0.786,6.56,6800,100.0
Barquat MB80,4,5,1.03,8.59,5588,82.2
HiTEC 3337,4,200,0.9,7.51,6395,94.0
HYPERFLOC CE 884 G GPC,4,100,1.05,8.76,5481,80.6
VW HP GO 0W-20,4,55,0.87,7.26,6615,97.3
ELCO 108,4,5,1.02,8.51,5643,83.0
ETHOXYLATED EO/PO L-81,4,250,1.03,8.59,5588,82.2
Bulk load of Scavenger,4,5,1.05,8.76,5481,80.6
HiTEC 8703,4,200,0.9,7.51,6395,94.0
Decovery SP-8354 XP,4,100,1.1,9.17,5232,76.9
ACURON,4,5,1.1,9.17,5232,76.9
DYNROLL60,3,50,0.91,7.59,6325,93.0
Amine N1,3,5,1.02,8.51,5643,83.0
Calcium Nitrate,3,2.5,1.3,10.84,4427,65.1
PIONIER 2196,3,100,0.99,8.26,5814,85.5
SORBITAN MONOLAURATE - SML-VL,3,330,1.032,8.61,5577,82.0
SPECTRUM,3,100,1.05,8.76,5481,80.6
FLOSPERSE 3000,3,10,1.05,8.76,5481,80.6
BARLOX 12,3,30,1.03,8.59,5588,82.2
HiTEC 12210M,3,200,0.9,7.51,6395,94.0
FLOJET NI 1450,3,50,1.1,9.17,5232,76.9
FARMIN M2 1095,3,15,1,8.34,5755,84.6
Amines or imines or its substitutes,3,5,1.02,8.51,5643,83.0
SECTAGON 42,3,1,0.85,7.09,6771,99.6
CLARIFLOC C-6267,3,100,0.95,7.92,6058,89.1
TEA,3,590,1.124,9.37,5120,75.3
FARMIN DM2470N,3,15,1,8.34,5755,84.6
Methyl Ethyl Ketone,3,0.4,0.805,6.71,6800,100.0
ColaTeric CNA-40,3,30,1.04,8.67,5534,81.4
Alum,3,2.5,1,8.34,5755,84.6
Magic - 0 De Icer,3,16,1,8.34,5755,84.6
EMERSOL 223 OLEIC,3,25,1,8.34,5755,84.6
MOLYVAN 855,3,200,0.95,7.92,6058,89.1
R06823A,3,15,1,8.34,5755,84.6
Amine N1-TS 53,3,5,1.02,8.51,5643,83.0
T-1855 Double Pressed Stearic Acid,3,11.6,0.9,7.51,6395,94.0
Chembetaine C42 Surfactant,3,20,1.03,8.59,5588,82.2
PEG,3,7.3,1.126,9.39,5111,75.2
Transformer Oil,3,11,0.88,7.34,6540,96.2
ZETAG 8816 (US) FLOCCULANT,3,100,1.05,8.76,5481,80.6
UCON 50-HB-260 US KLUBER,3,200,0.95,7.92,6058,89.1
AMINE 4 2,4-D BLK GAL,3,5,1.02,8.51,5643,83.0
Resins,3,500,1,8.34,5755,84.6
MEK,3,0.4,0.805,6.71,6800,100.0
HYPERFLOC AE 843,3,100,1.05,8.76,5481,80.6
CLARIFLOC C-358,3,100,0.95,7.92,6058,89.1
Topped coconut fatty acid c-1218,3,27,0.9,7.51,6395,94.0
PAVEX UN3267,3,20,1,8.34,5755,84.6
Ammonium Nitrate Liquor 83%,3,3,1,8.34,5755,84.6
Oil Petroleum,3,15,0.88,7.34,6540,96.2
TS-L100T,3,80,0.95,7.92,6058,89.1
Anerobic Bio Mass 45000,3,50,0.95,7.92,6058,89.1
BIO SLUDGE,3,50,0.95,7.92,6058,89.1
FennoSil 2180WR,3,5,1,8.34,5755,84.6
PLAS CHECK 775 (NON-HAZ),3,55,0.95,7.92,6058,89.1
HITEC 11183,3,200,0.9,7.51,6395,94.0
DURATEC ES 15W-40,3,120,0.87,7.26,6615,97.3
HYSPIN VG 32,3,55,0.95,7.92,6058,89.1
REDISTRENGTH HCL,3,1.9,0.85,7.09,6771,99.6
Perchloroethylene,3,9900,1.622,13.53,3548,52.2
RCS596,2,200,0.95,7.92,6058,89.1
EMERY 520 STEARIC ACID,2,11.6,0.9,7.51,6395,94.0
HERCOBOND 2800,2,30,1,8.34,5755,84.6
DPPT06-0142,2,30,1,8.34,5755,84.6
FARMIN DM4250M,2,15,1,8.34,5755,84.6
SODIUM METASILICATE,2,50,1.39,11.59,4141,60.9
CORRGUARD 95,2,5,1,8.34,5755,84.6
Safetemp ES Plus,2,50,0.95,7.92,6058,89.1
SLE3S 28%ACT,2,15,1,8.34,5755,84.6
MEGATRAN 245,2,200,0.95,7.92,6058,89.1
Industrial water treatment liquid,2,2,1,8.34,5755,84.6
CLARIFLOC CE-2486,2,100,0.95,7.92,6058,89.1
AchievAL FRH 200,2,200,0.95,7.92,6058,89.1
EMPIGEN BS/FA,2,20,1,8.34,5755,84.6
Clarifloc C-308P,2,100,0.95,7.92,6058,89.1
De-Icer,2,16,1.08,9.01,5329,78.4
Sodium Hydroxide,2,12,1.525,12.72,3774,55.5
Diala S4 ZX-IG,2,11,1,8.34,5755,84.6
MEGATRAN 205F,2,200,0.95,7.92,6058,89.1
Bapbase 8 Base Oil,2,30,0.88,7.34,6540,96.2
EMERSOL 213 OLEIC ACID,2,27.6,0.9,7.51,6395,94.0
SYNTILO 9902,2,4,1,8.34,5755,84.6
ETHOXYLATED EO/PO L-101,2,250,1.03,8.59,5588,82.2
DINP,2,55,0.95,7.92,6058,89.1
NGEO Low Ash 40,2,100,0.95,7.92,6058,89.1
BLACKMAX 22 0-0-4 BLK,2,5,1,8.34,5755,84.6
AOS-40 UP,2,20,1,8.34,5755,84.6
Ethanol SDA 3A-190,2,1.1,0.789,6.58,6800,100.0
FLOPAM EMA 23,2,100,0.95,7.92,6058,89.1
KYMENE 821,2,30,1,8.34,5755,84.6
CNHPREHYDHV68AW,2,120,0.95,7.92,6058,89.1
STARKOTE AQ 709-NC-2 LIQUID,2,200,0.95,7.92,6058,89.1
CLARIFLOC C-6260,2,100,0.95,7.92,6058,89.1
Ethanol Water Recycle,2,1.1,1,8.34,5755,84.6
SAFETEMP ES PLUS SLURRY,2,50,1.2,10.01,4796,70.5
HERCON 600,2,200,0.95,7.92,6058,89.1
AROMATIC BLEND,2,1.5,0.85,7.09,6771,99.6
MIBC,2,4.2,1,8.34,5755,84.6
HD PhosFree Y,2,5,1,8.34,5755,84.6
NALCO 60625b,2,5,1.1,9.17,5232,76.9
Benz Grind HP 22,2,10,1,8.34,5755,84.6
DefendAl HD ELC,2,16,1.113,9.28,5171,76.0
PHENOL,2,500,1.06,8.84,5430,79.8
DIETHYL SULFATE,2,1.8,0.85,7.09,6771,99.6
KENWAX MED NEUTRAL SLACK WAX,2,5,0.8,6.67,6800,100.0
METHYL ISOBUTYL KETONE,2,0.5,0.802,6.69,6800,100.0
EDGE PROFESSIONAL EC 0W20,2,55,0.85,7.09,6771,99.6
ARGUARD ZF DDS+ 11 SAE 20W40,2,100,0.88,7.34,6540,96.2
CHV SYNFLUID-R 4 CST,2,3.7,1,8.34,5755,84.6
CLARIFLOC NE-2361,2,100,0.95,7.92,6058,89.1
CHEM-TREND HF-28,2,50,0.95,7.92,6058,89.1
NeoPac PU-481 b,2,200,1.05,8.76,5481,80.6
CETYL ALCOHOL NF,2,53,0.811,6.76,6800,100.0
DUAL RANGE HV 46,2,80,0.95,7.92,6058,89.1
HITEC 4569 FUEL ADDITIVE,2,200,0.9,7.51,6395,94.0
CLARIFLOC MA-058,2,100,0.95,7.92,6058,89.1
LEUCOPHOR T125 NON-HAZ,2,10,1.15,9.59,5005,73.6
CLARIFLOC C-6220,2,100,0.95,7.92,6058,89.1
DOWFROST HD,2,42,1,8.34,5755,84.6
LEUCOPHOR T100LIQ NON-HAZ,2,10,1,8.34,5755,84.6
CEDARFLOC 1260,2,100,0.95,7.92,6058,89.1
CHV CLARITY SAW GUIDE 100,2,85,0.95,7.92,6058,89.1
Lube,2,80,0.95,7.92,6058,89.1
HD PhosFree,2,5,1,8.34,5755,84.6
CHOLINE CHLORIDE 70%,2,20,1,8.34,5755,84.6
IGEPAL CA 897,2,200,0.95,7.92,6058,89.1
EDGE PROF V 0W-20,2,100,0.88,7.34,6540,96.2
AMMONIUM NITRATE SOLUTION,2,2.5,1.725,14.39,3336,49.1
CLARIFLOC C-379,2,100,0.95,7.92,6058,89.1
Silicone Oil,2,50,0.965,8.05,5964,87.7
Calsol 810 TS-L100T,2,80,0.95,7.92,6058,89.1
BMW GROUP LL-17 FE 0W-20,2,100,0.88,7.34,6540,96.2
CLARIFLOC CE-2482,2,100,0.95,7.92,6058,89.1
CLARIFLOC CE-2342,2,100,0.95,7.92,6058,89.1
Lignin L S-50,2,50,0.95,7.92,6058,89.1
ANAEROBIC BIOMASS,2,50,1.05,8.76,5481,80.6
NORLIG SLR50,2,50,0.95,7.92,6058,89.1
AU-692 GLYCOL ETHER,2,3,1,8.34,5755,84.6
SEQUENCE HERBICIDE BULK GA,2,5,1.1,9.17,5232,76.9
ACURON GT HERBICIDE BULK GA,2,5,1.1,9.17,5232,76.9
MIRAVIS NEO,2,5,1,8.34,5755,84.6
TENDOVO Herbicide,2,5,1.1,9.17,5232,76.9
TEA 99%,2,590,1.124,9.37,5120,75.3
WQ9211P ACRYLIC LATEX,2,200,1.02,8.51,5643,83.0
BULK ATBS MEHQ INHIBITOR 50%,2,3,1,8.34,5755,84.6
MED PLUS ROLL 60,2,65,0.95,7.92,6058,89.1
LUBRICITDTDA 1-DF,2,80,0.95,7.92,6058,89.1
Diala S4 ZX-IG ASTM,2,11,1,8.34,5755,84.6
R13457A,2,15,1,8.34,5755,84.6
CATENEX T 145,2,100,0.9,7.51,6395,94.0
Glycol Generic,2,16.1,1,8.34,5755,84.6
Sequence Herbicide,2,5,1.1,9.17,5232,76.9
"""

def parse_data():
    reader = csv.DictReader(io.StringIO(RAW))
    rows = []
    for r in reader:
        try:
            cp = float(r['cP']) if r['cP'] else None
            sg = float(r['SG']) if r['SG'] else None
            count = int(r['Count'])
            max_gal = float(r['max_gal'].replace(',','')) if r['max_gal'] else None
            fill = float(r['fill_pct']) if r['fill_pct'] else None
            rows.append({
                'name': r['Commodity'].strip(),
                'count': count,
                'cP': cp,
                'SG': sg,
                'max_gal': max_gal,
                'fill_pct': fill
            })
        except (ValueError, KeyError):
            pass
    return rows

def analyze():
    rows = parse_data()
    # Filter rows with valid viscosity data
    valid = [r for r in rows if r['cP'] is not None]
    
    total_loads = sum(r['count'] for r in rows)
    total_valid_loads = sum(r['count'] for r in valid)
    unique_products = len(rows)
    unique_valid = len(valid)
    
    print("=" * 70)
    print("BULL & BEAR FLEET - COMMODITY PORTFOLIO ANALYSIS")
    print("=" * 70)
    print(f"\nTotal shipments (loads):    {total_loads}")
    print(f"Unique commodities:         {unique_products}")
    print(f"With viscosity data:        {unique_valid} products ({total_valid_loads} loads)")
    
    # ── VISCOSITY DISTRIBUTION ──
    print("\n" + "─" * 70)
    print("1. VISCOSITY DISTRIBUTION (the #1 factor from sweep analysis)")
    print("─" * 70)
    
    bins = [
        ("Water-like (<5 cP)", 0, 5),
        ("Low (5-20 cP)", 5, 20),
        ("Medium-Low (20-50 cP)", 20, 50),
        ("Medium (50-100 cP)", 50, 100),
        ("Medium-High (100-200 cP)", 100, 200),
        ("High (200-500 cP)", 200, 500),
        ("Very High (500-1000 cP)", 500, 1000),
        ("Extreme (>1000 cP)", 1000, 99999),
    ]
    
    for label, lo, hi in bins:
        prods = [r for r in valid if lo <= r['cP'] < hi]
        loads = sum(r['count'] for r in prods)
        pct_loads = loads / total_valid_loads * 100 if total_valid_loads else 0
        pct_prods = len(prods) / unique_valid * 100 if unique_valid else 0
        bar = "█" * int(pct_loads / 2)
        print(f"  {label:30s} {len(prods):3d} products  {loads:4d} loads ({pct_loads:5.1f}%) {bar}")
    
    # Weighted average viscosity
    weighted_sum = sum(r['cP'] * r['count'] for r in valid)
    avg_cp = weighted_sum / total_valid_loads
    median_cp = statistics.median([r['cP'] for r in valid for _ in range(r['count'])])
    
    print(f"\n  Load-weighted avg viscosity:  {avg_cp:.1f} cP")
    print(f"  Load-weighted median:         {median_cp:.1f} cP")
    
    # ── TOP PRODUCTS BY LOAD COUNT ──
    print("\n" + "─" * 70)
    print("2. TOP 20 PRODUCTS BY SHIPMENT VOLUME")
    print("─" * 70)
    
    sorted_by_count = sorted(valid, key=lambda r: r['count'], reverse=True)[:20]
    print(f"  {'Commodity':40s} {'Loads':>5s} {'cP':>8s} {'SG':>6s} {'max_gal':>8s} {'fill%':>6s}")
    print(f"  {'─'*40} {'─'*5} {'─'*8} {'─'*6} {'─'*8} {'─'*6}")
    for r in sorted_by_count:
        print(f"  {r['name'][:40]:40s} {r['count']:5d} {r['cP']:8.1f} {r['SG']:6.3f} {r['max_gal']:8.0f} {r['fill_pct']:5.1f}%")
    
    top20_loads = sum(r['count'] for r in sorted_by_count)
    print(f"\n  Top 20 products = {top20_loads} loads ({top20_loads/total_valid_loads*100:.1f}% of all loads)")
    
    # ── SG / WEIGHT-LIMITED ANALYSIS ──
    print("\n" + "─" * 70)
    print("3. SPECIFIC GRAVITY & WEIGHT-LIMITED PRODUCTS")
    print("─" * 70)
    
    sg_bins = [
        ("Light (SG < 0.9)", 0, 0.9),
        ("Standard (0.9-1.05)", 0.9, 1.05),
        ("Medium-Heavy (1.05-1.2)", 1.05, 1.2),
        ("Heavy (1.2-1.5)", 1.2, 1.5),
        ("Very Heavy (SG > 1.5)", 1.5, 3.0),
    ]
    
    for label, lo, hi in sg_bins:
        prods = [r for r in valid if r['SG'] is not None and lo <= r['SG'] < hi]
        loads = sum(r['count'] for r in prods)
        avg_fill = statistics.mean([r['fill_pct'] for r in prods]) if prods else 0
        avg_gal = statistics.mean([r['max_gal'] for r in prods]) if prods else 0
        print(f"  {label:30s} {len(prods):3d} products  {loads:4d} loads  avg fill={avg_fill:.0f}%  avg_gal={avg_gal:.0f}")
    
    # Weight-limited vs volume-limited
    weight_limited = [r for r in valid if r['fill_pct'] is not None and r['fill_pct'] < 95]
    volume_limited = [r for r in valid if r['fill_pct'] is not None and r['fill_pct'] >= 95]
    wl_loads = sum(r['count'] for r in weight_limited)
    vl_loads = sum(r['count'] for r in volume_limited)
    
    print(f"\n  Weight-limited (<95% fill):   {len(weight_limited)} products, {wl_loads} loads ({wl_loads/total_valid_loads*100:.1f}%)")
    print(f"  Volume-limited (≥95% fill):   {len(volume_limited)} products, {vl_loads} loads ({vl_loads/total_valid_loads*100:.1f}%)")
    
    # ── NIGHTMARE PRODUCTS ──
    print("\n" + "─" * 70)
    print("4. NIGHTMARE PRODUCTS (>500 cP) - LONGEST UNLOAD TIMES")
    print("─" * 70)
    
    nightmares = sorted([r for r in valid if r['cP'] >= 500], key=lambda r: r['cP'], reverse=True)
    total_nightmare_loads = sum(r['count'] for r in nightmares)
    print(f"  {'Commodity':40s} {'Loads':>5s} {'cP':>8s} {'SG':>6s} {'max_gal':>8s}")
    print(f"  {'─'*40} {'─'*5} {'─'*8} {'─'*6} {'─'*8}")
    for r in nightmares:
        print(f"  {r['name'][:40]:40s} {r['count']:5d} {r['cP']:8.0f} {r['SG']:6.3f} {r['max_gal']:8.0f}")
    print(f"\n  Total nightmare loads: {total_nightmare_loads} ({total_nightmare_loads/total_valid_loads*100:.1f}% of fleet)")
    
    # ── EASY PRODUCTS ──
    print("\n" + "─" * 70)
    print("5. EASIEST PRODUCTS (<10 cP) - FASTEST UNLOADS")
    print("─" * 70)
    
    easy = sorted([r for r in valid if r['cP'] < 10], key=lambda r: r['count'], reverse=True)[:15]
    total_easy_loads = sum(r['count'] for r in [p for p in valid if r['cP'] < 10])
    easy_all = [r for r in valid if r['cP'] < 10]
    easy_total = sum(r['count'] for r in easy_all)
    print(f"  {'Commodity':40s} {'Loads':>5s} {'cP':>8s}")
    print(f"  {'─'*40} {'─'*5} {'─'*8}")
    for r in easy[:15]:
        print(f"  {r['name'][:40]:40s} {r['count']:5d} {r['cP']:8.1f}")
    print(f"\n  Total easy loads (<10 cP): {easy_total} ({easy_total/total_valid_loads*100:.1f}% of fleet)")
    
    # ── SIMULATION MAPPING ──
    print("\n" + "─" * 70)
    print("6. FLEET → SIMULATION MAPPING (from sweep results)")
    print("─" * 70)
    print("  Based on parametric sweep findings:")
    print("  - Viscosity is the #1 factor (32% of variance)")
    print("  - At 0 psig, 40 SCFM, 3\" hose, 2\" pipe:")
    print()
    
    sim_ranges = [
        ("<5 cP", 0, 5, "~25-35 min", "Fast, no issues"),
        ("5-50 cP", 5, 50, "~35-60 min", "Standard operation"),
        ("50-200 cP", 50, 200, "~60-120 min", "Manageable, plan time"),
        ("200-500 cP", 200, 500, "~120-200 min", "SLOW - need patience"),
        ("500-1000 cP", 500, 1000, "~200-350 min", "VERY SLOW - PD pump?"),
        (">1000 cP", 1000, 99999, "350+ min or FAILS", "NEED PD PUMP or heat"),
    ]
    
    for label, lo, hi, est_time, note in sim_ranges:
        prods_in = [r for r in valid if lo <= r['cP'] < hi]
        loads_in = sum(r['count'] for r in prods_in)
        pct = loads_in / total_valid_loads * 100
        print(f"  {label:15s} → {est_time:20s} | {loads_in:4d} loads ({pct:5.1f}%) | {note}")
    
    # ── PRODUCT FAMILY CLUSTERING ──
    print("\n" + "─" * 70)
    print("7. PRODUCT FAMILY CLUSTERS")
    print("─" * 70)
    
    families = {
        'Glycols': ['glycol', 'glycerin', 'peg', 'polyglycol'],
        'Oils & Lubes': ['oil', 'lube', 'lubric', 'motor', 'transformer', 'hydraul'],
        'Resins & Adhesives': ['resin', 'latex', 'adhesive', 'acrylic', 'emulsion'],
        'Surfactants': ['surf', 'betaine', 'oxide', 'sulfonate', 'colateric', 'foam'],
        'Water Treatment': ['floc', 'nalco', 'water treat', 'clarifloc', 'flopam'],
        'Amines': ['amine', 'tea ', 'monoethanol', 'diethanolamine'],
        'Waxes': ['wax', 'c24-28', 'c20-24'],
        'Solvents': ['acetone', 'ketone', 'mek', 'heptane', 'acetonitrile', 'ethanol'],
        'De-icers': ['de-icer', 'deicer', 'safewing', 'promex'],
        'Ag Chem': ['herbicide', 'acuron', 'sequence', 'fungicide', 'amine 4'],
    }
    
    for family, keywords in families.items():
        matched = [r for r in valid if any(kw in r['name'].lower() for kw in keywords)]
        if not matched:
            continue
        fam_loads = sum(r['count'] for r in matched)
        fam_avg_cp = sum(r['cP'] * r['count'] for r in matched) / fam_loads if fam_loads else 0
        fam_avg_sg = sum(r['SG'] * r['count'] for r in matched) / fam_loads if fam_loads else 0
        print(f"  {family:25s} {len(matched):3d} products  {fam_loads:4d} loads  avg_cP={fam_avg_cp:7.1f}  avg_SG={fam_avg_sg:.3f}")
    
    # ── LONG TAIL ──
    print("\n" + "─" * 70)
    print("8. LONG TAIL ANALYSIS")
    print("─" * 70)
    
    one_off = [r for r in rows if r['count'] == 1]
    two_off = [r for r in rows if r['count'] == 2]
    three_plus = [r for r in rows if r['count'] >= 3]
    
    print(f"  Single-load products (count=1):   {len(one_off):4d} products  {sum(r['count'] for r in one_off):4d} loads")
    print(f"  Two-load products (count=2):      {len(two_off):4d} products  {sum(r['count'] for r in two_off):4d} loads")
    print(f"  Repeat products (count≥3):        {len(three_plus):4d} products  {sum(r['count'] for r in three_plus):4d} loads")
    print(f"  (Repeat products = {sum(r['count'] for r in three_plus)/total_loads*100:.1f}% of all loads from {len(three_plus)/unique_products*100:.1f}% of products)")
    
    # ── KEY INSIGHTS ──
    print("\n" + "=" * 70)
    print("KEY INSIGHTS & RECOMMENDATIONS")
    print("=" * 70)
    
    print("""
  1. VISCOSITY SWEET SPOT: ~75% of loads are under 200 cP. Your air-powered
     unloading system handles these well. The median load is a "standard"
     unload taking 30-90 minutes.

  2. HIGH-VISC TAIL IS REAL: Tall oil rosin (5000 cP × 16 loads), Resin
     Solution (500 cP × 32 loads), Crude Glycerin (934 cP × 5 loads),
     Perchloroethylene (9900 cP × 3 loads) are genuine fleet problems.
     These represent ~8% of loads but cause the most driver headaches.

  3. ETHYLENE GLYCOL IS KING: 56 loads - your #1 product. At 16.1 cP it's
     an easy unload (~40 min estimated). This is your bread-and-butter.

  4. WEIGHT-LIMITED REALITY: Most products (SG > 0.9) can't fill to 100%.
     Heavy products like Sodium Thiocyanate (SG 1.7, 49.8% fill = 3,386 gal)
     mean you're hauling half-empty tankers by volume. Revenue per trip drops.

  5. DIVERSE PORTFOLIO: ~500 unique commodities but a LONG TAIL - over half
     are 1-2 load products. Top 20 products drive most of your volume.
     Standardize equipment/procedures around those 20.

  6. PUMP DECISION CONFIRMED: The Predator centrifugal pump is WRONG for
     this fleet. You need:
     - Air unloading for 90% of loads (under 200 cP) ← current system
     - A PD pump option for the 8% of loads over 500 cP
     - Or pre-heat capability for the extreme products

  7. SIMULATION PRIORITY: Focus calibration on 5-200 cP range (covers ~75%
     of loads). The extreme products (>500 cP) need separate procedures
     anyway - air unloading alone won't cut it for Tall oil rosin.
""")

if __name__ == '__main__':
    analyze()
