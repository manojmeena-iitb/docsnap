"""Make the generated half of the test set: 20 Indian bills whose correct answers are known exactly.

Each bill is drawn from the same numbers that go into its answer key, so the key is correct by
construction. Every bill has its own fixed random seed, so each run writes the same files.
Names, addresses and GSTINs are made up.
  uv run python scripts/make_sample_invoices.py
"""

import io
import json
import random
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from review_ground_truth import indian_number

rl_config.invariant = 1  # no timestamps inside the PDFs, so every run writes identical files

DOCS = Path("data/eval/docs")
KEYS = Path("data/eval/ground_truth")
SEED = 2026
PAISE = Decimal("0.01")
RUPEE = Decimal("1")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Catalogues: (description, HSN/SAC, GST %, lowest price, highest price, lowest qty, highest qty)
OFFICE = [
    ("A4 Copier Paper 75 GSM (Ream of 500)", "4802", 12, 240, 320, 5, 40),
    ("Ball Pen Blue (Box of 10)", "9608", 18, 50, 90, 5, 20),
    ("Whiteboard Marker Black", "9608", 18, 25, 40, 10, 50),
    ("LED Bulb 9W", "8539", 12, 80, 120, 10, 60),
    ("Extension Board 4 Socket", "8536", 18, 250, 400, 2, 12),
    ("Office Chair Mesh Back", "9401", 18, 3500, 5500, 2, 10),
    ("Wireless Mouse", "8471", 18, 450, 800, 5, 25),
    ("Printer Toner Cartridge", "8443", 18, 1800, 3200, 2, 8),
    ("Steel Almirah 6 ft", "9403", 18, 9000, 14000, 1, 4),
    ("First Aid Kit", "3006", 12, 600, 900, 2, 10),
    ("Notebook 200 Pages", "4820", 12, 40, 70, 20, 200),
    ("Hand Sanitizer 500 ml", "3808", 18, 150, 250, 5, 30),
]
IT = [
    ("Laptop 14 inch Core i5 16GB 512GB SSD", "8471", 18, 48000, 62000, 2, 10),
    ("Monitor 24 inch LED", "8528", 18, 8500, 12500, 2, 10),
    ("UPS 1 KVA", "8504", 18, 3800, 5200, 2, 8),
    ("Network Switch 24 Port", "8517", 18, 9500, 15000, 1, 4),
    ("Cat6 LAN Cable (305 m Box)", "8544", 18, 7500, 11000, 1, 5),
    ("Keyboard and Mouse Combo", "8471", 18, 900, 1500, 5, 20),
    ("Wi-Fi Access Point", "8517", 18, 6500, 9800, 2, 8),
    ("External Hard Disk 1 TB", "8471", 18, 3800, 4900, 2, 6),
]
AMC = [("Annual Maintenance Contract - Computers (Apr to Mar)", "998713", 18, 25000, 90000, 1, 1)]
DISHES = [(name, "996331", 5, lo, hi, 1, 3) for name, lo, hi in [
    ("Masala Dosa", 80, 140), ("Idli Vada", 50, 90), ("Paneer Butter Masala", 220, 320),
    ("Butter Naan", 40, 70), ("Veg Biryani", 180, 280), ("Dal Tadka", 160, 240),
    ("Jeera Rice", 140, 200), ("Filter Coffee", 30, 60), ("Sweet Lassi", 60, 110),
    ("Gulab Jamun (2 pcs)", 60, 100), ("Chicken 65", 240, 340), ("Fish Curry Meals", 220, 320),
    ("Tandoori Roti", 25, 45), ("Fresh Lime Soda", 60, 100), ("Veg Manchurian", 180, 260),
]]
GROCERY = [(name, "", gst, lo, hi, 1, 3) for name, gst, lo, hi in [  # prices include GST (MRP)
    ("Basmati Rice 5 kg", 5, 520, 780), ("Sunflower Oil 1 L", 5, 140, 190), ("Tea Powder 500 g", 5, 220, 290),
    ("Toothpaste 150 g", 18, 95, 140), ("Bath Soap 100 g (Pack of 4)", 18, 140, 220),
    ("Detergent Powder 1 kg", 18, 110, 160), ("Biscuits 200 g", 18, 30, 50), ("Shampoo 180 ml", 18, 160, 230),
    ("Instant Noodles (Pack of 6)", 12, 84, 96),
]]
MEDICINES = [(name, "", gst, lo, hi, 1, 3) for name, gst, lo, hi in [
    ("Paracetamol 500 mg (Strip of 15)", 12, 25, 40), ("Cough Syrup 100 ml", 12, 95, 140),
    ("Crepe Bandage 10 cm", 12, 110, 160), ("Antiseptic Liquid 250 ml", 18, 120, 170),
    ("Vitamin C Tablets (Strip of 15)", 18, 35, 60), ("ORS Sachet (Pack of 5)", 12, 90, 120),
]]
UNTAXED = [(name, "", 0, lo, hi, 1, 4) for name, lo, hi in [  # sold under a bill of supply: no GST charged
    ("Wheat Atta 10 kg", 380, 480), ("Toor Dal 1 kg", 140, 180), ("Sugar 5 kg", 220, 260),
    ("Groundnut Oil 1 L", 170, 210), ("Besan 1 kg", 90, 120), ("Poha 1 kg", 60, 80), ("Jaggery 1 kg", 70, 95),
]]

# Parties: (name, address lines, city and PIN, state, state code). All made up.
PUNE_TRADERS = ("Shree Ganesh Traders", ["Plot 22, MIDC Bhosari"], "Pune 411026", "Maharashtra", "27")
BLR_OFFICE = ("Kaveri Office Supplies", ["45, 2nd Cross, Jayanagar 4th Block"], "Bengaluru 560011", "Karnataka", "29")
HYD_SERVICE = ("Annapurna IT Services", ["12-2-831, Mehdipatnam"], "Hyderabad 500028", "Telangana", "36")
CHN_COMPUTERS = ("Meenakshi Computers", ["21, Anna Salai", "Teynampet"], "Chennai 600018", "Tamil Nadu", "33")
NOIDA_INFOTECH = ("Nexa Infotech Solutions Pvt Ltd", ["B-42, Sector 63"], "Noida 201301", "Uttar Pradesh", "09")
DELHI_ELECTRICALS = ("Sharma Electricals", ["Shop 14, Karol Bagh Market"], "New Delhi 110005", "Delhi", "07")
KOL_STATIONERS = ("Bengal Stationery Mart", ["7B, College Street"], "Kolkata 700073", "West Bengal", "19")
AMD_SYSTEMS = ("Sabarmati Computer Systems", ["301, Ashram Road"], "Ahmedabad 380009", "Gujarat", "24")
SPICE_ROUTE = ("Spice Route Kitchen", ["14, 100 Feet Road, Indiranagar"], "Bengaluru 560038", "Karnataka", "29")
COASTAL_CURRY = ("Coastal Curry House", ["Opp. Bus Stand, MG Road"], "Mangaluru 575001", "Karnataka", "29")
DHABA = ("Punjabi Tadka Family Dhaba", ["NH 44, Murthal"], "Sonipat 131027", "Haryana", "06")
GREEN_LEAF = ("Green Leaf Veg Restaurant", ["2-1-56, Nallakunta"], "Hyderabad 500044", "Telangana", "36")
CAFE_TULSI = ("Cafe Tulsi", ["5, FC Road, Shivajinagar"], "Pune 411004", "Maharashtra", "27")
TEMPLE_CITY = ("Temple City Meals", ["Near Clock Tower, West Masi Street"], "Madurai 625001", "Tamil Nadu", "33")
SUPERMART = ("Daily Needs Supermart", ["Shop 3, Sai Complex, Baner Road"], "Pune 411045", "Maharashtra", "27")
MEDICAL = ("Lakshmi Medical & General Stores", ["9, Gandhi Bazaar"], "Bengaluru 560004", "Karnataka", "29")
GENERAL_STORE = ("Gupta General Store", ["Main Bazaar, Lalbagh"], "Lucknow 226001", "Uttar Pradesh", "09")
FRESHCART = ("FreshCart Supermarket", ["Ground Floor, Plaza Complex, Kankarbagh"], "Patna 800020", "Bihar", "10")
KIRANA = ("Patel Kirana Store", ["12, Station Road, Maninagar"], "Ahmedabad 380008", "Gujarat", "24")
FLOUR_MILL = ("Nandini Flour Mill", ["Near Ram Mandir, Sadar"], "Nagpur 440001", "Maharashtra", "27")
SCHOOL = ("Greenfield Public School", ["Sector 21, Kharghar"], "Navi Mumbai 410210", "Maharashtra", "27")
ENGINEERING = ("Apex Engineering Works Pvt Ltd", ["Plot 7, Peenya Industrial Area"], "Bengaluru 560058", "Karnataka", "29")
HOSPITAL = ("Sunrise Multispeciality Hospital", ["Road No. 2, Banjara Hills"], "Hyderabad 500034", "Telangana", "36")
COLLEGE = ("Vidya Bharati College of Engineering", ["Hingna Road"], "Nagpur 440016", "Maharashtra", "27")
INSTITUTE = ("Riverbank Institute of Management", ["Plot 9, Patia"], "Bhubaneswar 751024", "Odisha", "21")
HOTEL = ("Lotus Valley Hotels Pvt Ltd", ["Fort Road"], "Kochi 682001", "Kerala", "32")
RAIL_SPARES = ("Eastern Rail Spares Pvt Ltd", ["22, Strand Road"], "Kolkata 700001", "West Bengal", "19")
AGRO = ("Deccan Agro Research Foundation", ["Shivajinagar"], "Pune 411005", "Maharashtra", "27")
CANTEEN = ("Sai Krupa Canteen", ["MIDC Hingna"], "Nagpur 440016", "Maharashtra", "27")


@dataclass
class Style:
    font: str = "Helvetica"          # Helvetica, Times or Courier
    numbers: str = "indian"          # indian 1,23,456.00 | western 123,456.00 | plain 123456.00
    date: str = "dd-mm-yyyy"
    columns: str = "full"            # full (HSN and GST % columns) or simple
    grid: bool = False               # vertical lines in the item table
    number_label: str = "Invoice No."
    total_label: str = "Grand Total"
    paise: bool = False              # prices with paise, not whole rupees
    round_total: bool = True         # round the total to the rupee and print the round-off
    tax_summary: bool = False        # Tally-style HSN tax table under the totals (repeats the tax)


@dataclass
class Bill:
    doc_id: str
    kind: str                        # gst_intra | gst_inter | retail | restaurant | bill_of_supply
    layout: str                      # a4 or receipt
    output: str                      # pdf (digital) or scan (picture of a printed page)
    seller: tuple
    buyer: tuple | None
    catalogue: list
    n_items: int
    number: str                      # pattern, e.g. "INV/{fy}/{n:04d}"
    style: Style = field(default_factory=Style)
    discount_pct: int = 0
    service_pct: int = 0
    freight: int = 0
    previous_due: bool = False       # print an older unpaid balance under the total (a trap)
    mistake: str | None = None       # wrong_total | wrong_item | bad_gstin | bad_date | total_skips_service
    note: str = ""


@dataclass
class Printed:
    """Every value that appears on the bill. The answer key is built from these, never recomputed."""
    title: str
    number: str
    ymd: tuple[int, int, int]
    seller_gstin: str
    buyer_gstin: str | None
    items: list[dict]
    items_total: Decimal
    freight: Decimal
    discount: Decimal | None
    service: Decimal | None
    tax_lines: list[tuple[str, Decimal]]
    tax_included: bool
    before_round: Decimal
    round_off: Decimal
    total: Decimal
    extras: dict = field(default_factory=dict)


BILLS = [
    Bill("gen_01", "gst_intra", "a4", "pdf", PUNE_TRADERS, SCHOOL, [OFFICE[i] for i in (0, 1, 3, 4, 9)], 5,
         "SGT/{fy}/{n:04d}",
         Style(tax_summary=True),
         note="Two GST rates (12% and 18%), each with its own CGST and SGST lines. The tax table repeats the tax amounts."),
    Bill("gen_02", "gst_intra", "a4", "scan", BLR_OFFICE, ENGINEERING, [x for x in OFFICE if x[2] == 18], 4, "KOS-{n}",
         Style(font="Times", numbers="western", date="d-Mon-yyyy", columns="simple", grid=True, total_label="Total"),
         discount_pct=5, note="Scanned page. A 5% discount comes off before tax."),
    Bill("gen_03", "gst_intra", "a4", "pdf", HYD_SERVICE, HOSPITAL, AMC, 1, "AS/{n:03d}/{fy}",
         Style(font="Courier", numbers="plain", date="dd/mm/yy", total_label="Invoice Total", paise=True, round_total=False),
         note="One service line, amounts without digit grouping, two-digit year."),
    Bill("gen_04", "gst_inter", "a4", "pdf", CHN_COMPUTERS, COLLEGE, IT, 3, "MC/{fy}/{n}",
         Style(date="d Mon yyyy", total_label="Total Amount", tax_summary=True),
         freight=1500, note="Interstate (IGST). Freight is taxed, so it is a line item; subtotal = taxable value."),
    Bill("gen_05", "gst_inter", "a4", "scan", NOIDA_INFOTECH, INSTITUTE, IT, 7, "NIS/{n:05d}",
         Style(font="Courier", date="dd.mm.yyyy", grid=True),
         note="Scanned page, seven items, total in lakhs."),
    Bill("gen_06", "gst_inter", "a4", "pdf", DELHI_ELECTRICALS, HOTEL, [OFFICE[3], OFFICE[4]], 2, "SE/{fy}/{n}",
         Style(font="Times", numbers="western", date="dd/mm/yyyy", columns="simple", total_label="Net Amount Payable",
               number_label="Bill No.", paise=True),
         previous_due=True, note="An older unpaid balance and a 'Total Due' are printed under the total: a trap."),
    Bill("gen_07", "retail", "receipt", "scan", SUPERMART, None, GROCERY, 6, "{n}",
         Style(numbers="western", date="dd/mm/yyyy", number_label="Bill No", total_label="NET AMOUNT"),
         note="Supermarket receipt photo. Prices include GST; the GST shown is already inside the total. 'You saved' is a trap."),
    Bill("gen_08", "retail", "receipt", "pdf", MEDICAL, None, MEDICINES, 4, "LM{n:05d}",
         Style(numbers="plain", date="dd-mm-yyyy", number_label="Bill No", total_label="Bill Amount"),
         note="Medical store receipt. Prices include GST (12% and 18%)."),
    Bill("gen_09", "retail", "a4", "pdf", GENERAL_STORE, None, GROCERY, 5, "GGS/{n}",
         Style(font="Times", date="d-Mon-yyyy", columns="simple", number_label="Bill No.", total_label="Total"),
         note="Shop invoice on A4. Prices include GST; the GST breakup is printed for information only."),
    Bill("gen_10", "restaurant", "receipt", "scan", SPICE_ROUTE, None, DISHES, 5, "{n}",
         Style(numbers="western", date="dd/mm/yy", number_label="Bill No", total_label="GRAND TOTAL"),
         service_pct=10, note="Restaurant receipt photo. 10% service charge; 5% GST is charged on food plus service charge."),
    Bill("gen_11", "restaurant", "receipt", "pdf", GREEN_LEAF, None, DISHES, 4, "GL/{n}",
         Style(numbers="plain", date="dd-mm-yyyy", number_label="Bill No", total_label="NET PAYABLE"),
         discount_pct=10, note="Restaurant receipt with a 10% discount before GST."),
    Bill("gen_12", "restaurant", "receipt", "scan", DHABA, None, DISHES, 6, "{n}",
         Style(numbers="western", date="d-Mon-yyyy", number_label="Inv No", total_label="TOTAL"),
         discount_pct=10, service_pct=5, note="Receipt photo with both a discount and a service charge."),
    Bill("gen_13", "restaurant", "receipt", "pdf", CAFE_TULSI, None, DISHES, 3, "CT-{n:04d}",
         Style(numbers="western", date="dd/mm/yyyy", number_label="Bill No", total_label="Amount Payable"),
         note="Small cafe bill: food, 5% GST and a round-off."),
    Bill("gen_14", "bill_of_supply", "a4", "pdf", FLOUR_MILL, CANTEEN, UNTAXED, 4, "BS/{fy}/{n:03d}",
         Style(columns="simple", total_label="Total"),
         note="Bill of supply from a composition dealer: no GST is charged, so tax is not printed."),
    Bill("gen_15", "bill_of_supply", "receipt", "scan", KIRANA, None, UNTAXED, 5, "{n}",
         Style(numbers="plain", date="dd/mm/yy", number_label="Bill No", total_label="TOTAL"),
         note="Kirana shop receipt photo, bill of supply: no GST."),
    Bill("gen_16", "gst_intra", "a4", "pdf", KOL_STATIONERS, RAIL_SPARES, OFFICE, 3, "BSM/{fy}/{n:04d}",
         Style(date="dd/mm/yyyy"), mistake="wrong_total",
         note="Deliberate mistake: the printed total is Rs. 100 more than subtotal + tax."),
    Bill("gen_17", "gst_inter", "a4", "scan", AMD_SYSTEMS, AGRO, IT, 4, "SCS-{n}",
         Style(font="Times", numbers="western", date="d-Mon-yyyy"), mistake="wrong_item",
         note="Deliberate mistake: one item amount has two digits swapped, so the items no longer add up to the subtotal."),
    Bill("gen_18", "restaurant", "receipt", "pdf", COASTAL_CURRY, None, DISHES, 4, "{n}",
         Style(numbers="western", date="dd-mm-yyyy", number_label="Bill No", total_label="TOTAL"), mistake="bad_gstin",
         note="Deliberate mistake: the GSTIN has a letter where a digit must be."),
    Bill("gen_19", "retail", "receipt", "pdf", FRESHCART, None, GROCERY, 4, "FC{n:06d}",
         Style(numbers="western", date="dd/mm/yyyy", number_label="Bill No", total_label="NET AMOUNT"),
         mistake="bad_date", note="Deliberate mistake: the date is 31/04/2025, and April has only 30 days."),
    Bill("gen_20", "restaurant", "receipt", "scan", TEMPLE_CITY, None, DISHES, 5, "{n}",
         Style(numbers="plain", date="dd/mm/yyyy", number_label="Bill No", total_label="TOTAL"),
         service_pct=10, mistake="total_skips_service",
         note="Deliberate mistake: the service charge is printed but left out of the total."),
]


# ---------- numbers, dates, GSTINs ----------

def money(value) -> Decimal:
    return Decimal(value).quantize(PAISE, ROUND_HALF_UP)


def show_amount(value: Decimal, style: Style) -> str:
    if style.numbers == "indian":
        return indian_number(float(value))
    if style.numbers == "western":
        return f"{value:,.2f}"
    return f"{value:.2f}"


def show_date(ymd: tuple[int, int, int], style: Style) -> str:
    y, m, d = ymd
    return {
        "dd-mm-yyyy": f"{d:02d}-{m:02d}-{y}", "dd/mm/yyyy": f"{d:02d}/{m:02d}/{y}",
        "dd/mm/yy": f"{d:02d}/{m:02d}/{y % 100:02d}", "dd.mm.yyyy": f"{d:02d}.{m:02d}.{y}",
        "d-Mon-yyyy": f"{d}-{MONTHS[m - 1]}-{y}", "d Mon yyyy": f"{d} {MONTHS[m - 1]} {y}",
    }[style.date]


def financial_year(ymd: tuple[int, int, int]) -> str:
    y, m, _ = ymd
    start = y if m >= 4 else y - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


def gstin_check_char(first14: str) -> str:
    """The 15th GSTIN character: a checksum over the first 14."""
    total = 0
    for i, char in enumerate(first14):
        product = GSTIN_CHARS.index(char) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def make_gstin(rng: random.Random, state_code: str) -> str:
    pan = "".join(rng.choice(LETTERS) for _ in range(3)) + rng.choice("CFP") + rng.choice(LETTERS)
    pan += f"{rng.randrange(10000):04d}" + rng.choice(LETTERS)
    first14 = f"{state_code}{pan}1Z"
    return first14 + gstin_check_char(first14)


def rupees_in_words(value: Decimal) -> str:
    """Indian style: 2,77,552.50 -> Rupees Two Lakh Seventy Seven Thousand ... and Fifty Paise Only."""
    ones = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen "
            "Fifteen Sixteen Seventeen Eighteen Nineteen").split()
    tens = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()

    def below_100(n):
        return ones[n] if n < 20 else tens[n // 10] + (f" {ones[n % 10]}" if n % 10 else "")

    def words(n):
        parts = []
        for size, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand"), (100, "Hundred")):
            if n >= size:
                parts.append(f"{words(n // size)} {name}")
                n %= size
        if n:
            parts.append(below_100(n))
        return " ".join(parts) or "Zero"

    rupees, paise = int(value), int((value - int(value)) * 100)
    text = f"Rupees {words(rupees)}"
    if paise:
        text += f" and {below_100(paise)} Paise"
    return text + " Only"


# ---------- the numbers on each bill ----------

def make_printed(bill: Bill) -> Printed:
    rng = random.Random(f"{SEED}:{bill.doc_id}")
    when = date(2024, 4, 1) + timedelta(days=rng.randrange((date(2026, 9, 30) - date(2024, 4, 1)).days))
    ymd = (when.year, when.month, when.day)
    number = bill.number.format(fy=financial_year(ymd), n=rng.randrange(1, 10000))

    items = []
    for desc, hsn, gst, lo, hi, qlo, qhi in rng.sample(bill.catalogue, bill.n_items):
        rate = Decimal(rng.randrange(lo, hi + 1))
        if bill.style.paise:
            rate += Decimal(rng.randrange(100)) / 100
        qty = Decimal(rng.randrange(qlo, qhi + 1))
        items.append({"description": desc, "hsn": hsn, "gst": gst, "qty": qty, "rate": rate, "amount": money(qty * rate)})
    items_total = sum(i["amount"] for i in items)

    freight = money(bill.freight)
    discount = money(items_total * bill.discount_pct / 100) if bill.discount_pct else None
    service = money((items_total - (discount or 0)) * bill.service_pct / 100) if bill.service_pct else None
    taxable = items_total - (discount or 0) + (service or 0) + freight

    tax_lines, tax_included = [], False
    if bill.kind in ("gst_intra", "gst_inter"):
        groups = defaultdict(Decimal)
        for i in items:
            groups[i["gst"]] += i["amount"]
        if discount:  # only used where every item has the same rate
            groups[items[0]["gst"]] -= discount
        if freight:
            groups[18] += freight
        for gst in sorted(groups):
            if bill.kind == "gst_intra":
                half = money(groups[gst] * gst / 200)
                tax_lines += [(f"CGST @ {gst / 2:g}%", half), (f"SGST @ {gst / 2:g}%", half)]
            else:
                tax_lines.append((f"IGST @ {gst}%", money(groups[gst] * gst / 100)))
    elif bill.kind == "restaurant":
        half = money(taxable * Decimal("0.025"))
        tax_lines = [("CGST @ 2.5%", half), ("SGST @ 2.5%", half)]
    elif bill.kind == "retail":  # MRP prices already include GST: show the GST inside them
        tax_included = True
        groups = defaultdict(Decimal)
        for i in items:
            groups[i["gst"]] += i["amount"]
        for gst in sorted(groups):
            inside = groups[gst] - groups[gst] * 100 / (100 + gst)
            half = money(inside / 2)
            tax_lines += [(f"CGST {gst / 2:g}% (incl.)", half), (f"SGST {gst / 2:g}% (incl.)", half)]

    before_round = taxable + (0 if tax_included else sum(a for _, a in tax_lines))
    total = before_round.quantize(RUPEE, ROUND_HALF_UP) if bill.style.round_total else before_round
    printed = Printed(
        title={"bill_of_supply": "BILL OF SUPPLY", "retail": "INVOICE"}.get(bill.kind, "TAX INVOICE"),
        number=number, ymd=ymd, seller_gstin=make_gstin(rng, bill.seller[4]),
        buyer_gstin=make_gstin(rng, bill.buyer[4]) if bill.buyer and bill.buyer is not SCHOOL else None,
        items=items, items_total=items_total, freight=freight, discount=discount, service=service,
        tax_lines=tax_lines, tax_included=tax_included, before_round=before_round,
        round_off=total - before_round, total=total,
        extras={"table": rng.randrange(1, 25), "covers": rng.randrange(1, 7),
                "time": f"{rng.randrange(11, 23):02d}:{rng.randrange(60):02d}",
                "fssai": f"1{rng.randrange(10**12, 10**13)}",
                "saved": money(items_total * Decimal(rng.randrange(4, 12)) / 100),
                "previous_due": money(rng.randrange(5000, 40000))},
    )
    return add_mistake(bill, printed, rng)


def add_mistake(bill: Bill, p: Printed, rng: random.Random) -> Printed:
    """Change one printed value so the bill breaks a check in SPEC.md."""
    if bill.mistake == "wrong_total":
        p = replace(p, total=p.total + 100)
    elif bill.mistake == "wrong_item":
        item = max(p.items, key=lambda i: i["amount"])
        digits = list(f"{int(item['amount'])}")
        k = next(k for k in range(len(digits) - 1) if digits[k] != digits[k + 1])
        digits[k], digits[k + 1] = digits[k + 1], digits[k]
        item["amount"] = Decimal("".join(digits)) + item["amount"] - int(item["amount"])
    elif bill.mistake == "bad_gstin":
        p = replace(p, seller_gstin=p.seller_gstin[:7] + "K" + p.seller_gstin[8:])
    elif bill.mistake == "bad_date":
        p = replace(p, ymd=(2025, 4, 31))
    elif bill.mistake == "total_skips_service":
        without = p.before_round - p.service
        total = without.quantize(RUPEE, ROUND_HALF_UP)
        p = replace(p, total=total, round_off=total - without)
    return p


def answer_key(bill: Bill, p: Printed) -> dict:
    line_items = [{"description": i["description"], "quantity": float(i["qty"]),
                   "unit_price": float(i["rate"]), "amount": float(i["amount"])} for i in p.items]
    if p.freight:
        line_items.append({"description": "Freight Charges", "quantity": None, "unit_price": None,
                           "amount": float(p.freight)})
    y, m, d = p.ymd
    return {
        "vendor_name": bill.seller[0],
        "invoice_number": p.number,
        "invoice_date": f"{y:04d}-{m:02d}-{d:02d}",
        "currency": "INR",
        "line_items": line_items,
        "subtotal": float(p.items_total + p.freight),
        "discount": float(p.discount) if p.discount else None,
        "service_charge": float(p.service) if p.service else None,
        "tax": float(sum(a for _, a in p.tax_lines)) if p.tax_lines else None,
        "total": float(p.total),
        "vendor_gstin": p.seller_gstin,
        "expected_status": "needs_review" if bill.mistake else "ok",
        "_meta": {
            "source": "Generated by scripts/make_sample_invoices.py",
            "licence": "Made for this project; names, addresses and GSTINs are made up",
            "original_id": f"seed {SEED}, {bill.doc_id}",
            "kind": bill.kind + (f"_mistake_{bill.mistake}" if bill.mistake else ""),
            "checked_by_hand": False,
            "draft_note": bill.note,
            "review": "Correct by construction: the document and this key are made from the same numbers.",
        },
    }


def build_keys() -> dict[str, dict]:
    """Every answer key, without drawing anything (used by the tests)."""
    return {bill.doc_id: answer_key(bill, make_printed(bill)) for bill in BILLS}


# ---------- drawing ----------

FONTS = {"Helvetica": ("Helvetica", "Helvetica-Bold"), "Times": ("Times-Roman", "Times-Bold"),
         "Courier": ("Courier", "Courier-Bold")}


class Pen:
    def __init__(self, c: canvas.Canvas, family: str):
        self.c = c
        self.regular, self.bold = FONTS[family]

    def text(self, x, y, s, size=9, bold=False, align="l"):
        self.c.setFont(self.bold if bold else self.regular, size)
        {"l": self.c.drawString, "r": self.c.drawRightString, "c": self.c.drawCentredString}[align](x, y, s)


def totals_rows(bill: Bill, p: Printed) -> list[tuple[str, Decimal]]:
    """The lines between the item table and the grand total, in print order."""
    rows = [("Sub Total", p.items_total)]
    if p.freight:
        rows += [("Freight Charges", p.freight), ("Taxable Value", p.items_total + p.freight)]
    if p.discount:
        rows.append((f"Less: Discount ({bill.discount_pct}%)", -p.discount))
    if p.service:
        rows.append((f"Service Charge ({bill.service_pct}%)", p.service))
    if not p.tax_included:
        rows += p.tax_lines
    if p.round_off:
        rows.append(("Round Off", p.round_off))
    return rows


def render_a4(bill: Bill, p: Printed) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pen, s = Pen(c, bill.style.font), bill.style
    width, height = A4
    left, right = 40, width - 40

    y = height - 50
    pen.text(width / 2, y, p.title, 14, True, "c")
    name, address, city, state, code = bill.seller
    y -= 30
    pen.text(left, y, name, 12, True)
    for line in [*address, city, f"GSTIN: {p.seller_gstin}", f"State: {state}, Code: {code}"]:
        y -= 12
        pen.text(left, y, line)
    if bill.kind == "bill_of_supply":
        y -= 12
        pen.text(left, y, "Composition taxable person, not eligible to collect tax on supplies", 8)
    ry = height - 80
    for label, value in [(s.number_label, p.number), ("Date", show_date(p.ymd, s))]:
        pen.text(360, ry, label)
        pen.text(440, ry, f": {value}", bold=True)
        ry -= 14
    if bill.kind == "gst_inter":
        pen.text(360, ry, "Place of Supply")
        pen.text(440, ry, f": {bill.buyer[3]} ({bill.buyer[4]})")

    y -= 26
    if bill.buyer:
        bname, baddress, bcity, bstate, bcode = bill.buyer
        pen.text(left, y, "Bill To:", bold=True)
        y -= 13
        pen.text(left, y, bname, 10, True)
        lines = [*baddress, bcity, f"GSTIN: {p.buyer_gstin or 'Unregistered'}", f"State: {bstate}, Code: {bcode}"]
        for line in lines:
            y -= 12
            pen.text(left, y, line)
    else:
        pen.text(left, y, "Customer: Cash", bold=True)
    y -= 22

    if s.columns == "full":
        cols = [("S.No", 24, "l"), ("Description", 196, "l"), ("HSN/SAC", 55, "l"), ("Qty", 40, "r"),
                ("Rate", 72, "r"), ("GST %", 40, "r"), ("Amount", 88, "r")]
    else:
        cols = [("S.No", 24, "l"), ("Description", 266, "l"), ("Qty", 50, "r"), ("Rate", 80, "r"), ("Amount", 95, "r")]
    edges = [left]
    for _, w, _ in cols:
        edges.append(edges[-1] + w)

    def row(values, yy, bold=False):
        for (_, w, align), x0, value in zip(cols, edges, values):
            pen.text(x0 + 3 if align == "l" else x0 + w - 3, yy, value, 9, bold, align)

    top = y + 12
    c.line(left, top, right, top)
    row([col[0] for col in cols], y, bold=True)
    c.line(left, y - 5, right, y - 5)
    y -= 18
    desc_width = cols[1][1] - 6
    for n, item in enumerate(p.items, 1):
        lines = simpleSplit(item["description"], pen.regular, 9, desc_width)
        values = {"S.No": str(n), "Description": lines[0], "HSN/SAC": item["hsn"], "Qty": f"{item['qty']:g}",
                  "Rate": show_amount(item["rate"], s), "GST %": f"{item['gst']}%",
                  "Amount": show_amount(item["amount"], s)}
        row([values[col[0]] for col in cols], y)
        for extra in lines[1:]:
            y -= 11
            pen.text(edges[1] + 3, y, extra)
        y -= 16
    c.line(left, y + 6, right, y + 6)
    if s.grid:
        for x in edges:
            c.line(x, top, x, y + 6)

    y -= 8
    for label, value in totals_rows(bill, p):
        pen.text(right - 220, y, label)
        pen.text(right, y, show_amount(value, s), align="r")
        y -= 14
    c.line(right - 220, y + 9, right, y + 9)
    y -= 4
    pen.text(right - 220, y, s.total_label, 11, True)
    pen.text(right, y, f"Rs. {show_amount(p.total, s)}", 11, True, "r")
    y -= 20
    if bill.previous_due:
        due = p.extras["previous_due"]
        for label, value in [("Previous Balance Due", due), ("Total Due", p.total + due)]:
            pen.text(right - 220, y, label)
            pen.text(right, y, show_amount(value, s), align="r")
            y -= 14
        y -= 6
    for line in simpleSplit(f"Amount in words: {rupees_in_words(p.total)}", pen.regular, 9, right - left):
        pen.text(left, y, line)
        y -= 12
    if p.tax_included:
        y -= 6
        pen.text(left, y, "Prices are inclusive of GST. GST included in the above amount:", 8)
        for label, value in p.tax_lines:
            y -= 11
            pen.text(left + 10, y, f"{label}: {show_amount(value, s)}", 8)

    if s.tax_summary:
        y -= 20
        intra = bill.kind == "gst_intra"
        heads = ["GST Rate", "Taxable Value"] + (["CGST", "SGST"] if intra else ["IGST"]) + ["Total Tax"]
        xs = [left + 60, left + 170, left + 260, left + 350, left + 440][:len(heads)]
        for head, x in zip(heads, xs):
            pen.text(x, y, head, 8, True, "r")
        rates = sorted({i["gst"] for i in p.items} | ({18} if p.freight else set()))
        for gst in rates:
            y -= 12
            base = sum(i["amount"] for i in p.items if i["gst"] == gst) + (p.freight if gst == 18 else 0)
            parts = [a for label, a in p.tax_lines if f"@ {gst / 2:g}%" in label or f"@ {gst}%" in label]
            cells = [f"{gst}%", show_amount(base, s)] + [show_amount(a, s) for a in parts]
            cells.append(show_amount(sum(parts), s))
            for cell, x in zip(cells, xs):
                pen.text(x, y, cell, 8, align="r")

    pen.text(left, 90, "Declaration: We declare that this invoice shows the actual price of the goods", 8)
    pen.text(left, 80, "described and that all particulars are true and correct.", 8)
    pen.text(right, 90, f"For {name}", 9, True, "r")
    pen.text(right, 55, "Authorised Signatory", 8, align="r")
    pen.text(width / 2, 35, "This is a computer generated invoice.", 7, align="c")
    c.showPage()
    c.save()
    return buf.getvalue()


def render_receipt(bill: Bill, p: Printed) -> bytes:
    """A narrow thermal-printer receipt (80 mm wide) in a fixed-width font."""
    s, width, left, right = bill.style, 226, 10, 216
    rows: list[list[tuple[float, str, str, bool]]] = []

    def center(text, bold=False):
        rows.append([(width / 2, text, "c", bold)])

    def pair(a, b, bold=False):
        rows.append([(left, a, "l", bold), (right, b, "r", bold)])

    def rule():
        rows.append([(left, "-" * 43, "l", False)])

    name, address, city, _, _ = bill.seller
    for line in textwrap.wrap(name.upper(), 34):
        center(line, True)
    for line in [*address, city]:
        center(line)
    center(f"GSTIN: {p.seller_gstin}")
    if bill.kind == "restaurant":
        center(f"FSSAI Lic. No. {p.extras['fssai']}")
    center("BILL OF SUPPLY" if bill.kind == "bill_of_supply" else "TAX INVOICE", True)
    rule()
    pair(f"{s.number_label}: {p.number}", f"Date: {show_date(p.ymd, s)}")
    if bill.kind == "restaurant":
        pair(f"Table: {p.extras['table']}  Covers: {p.extras['covers']}", f"Time: {p.extras['time']}")
    rule()
    rows.append([(left, "Item", "l", True), (112, "Qty", "r", True), (160, "Rate", "r", True), (right, "Amt", "r", True)])
    rule()
    for item in p.items:
        lines = textwrap.wrap(item["description"], 17)
        rows.append([(left, lines[0], "l", False), (112, f"{item['qty']:g}", "r", False),
                     (160, show_amount(item["rate"], s), "r", False), (right, show_amount(item["amount"], s), "r", False)])
        for extra in lines[1:]:
            rows.append([(left + 6, extra, "l", False)])
    rule()
    for label, value in totals_rows(bill, p):
        pair(label, show_amount(value, s))
    rule()
    pair(s.total_label, f"Rs. {show_amount(p.total, s)}", True)
    rule()
    if p.tax_included:
        center("Prices include GST. GST included:")
        for label, value in p.tax_lines:
            pair(f"  {label}", show_amount(value, s))
        center(f"Items: {len(p.items)}  Qty: {sum(i['qty'] for i in p.items):g}")
        center(f"You saved Rs. {show_amount(p.extras['saved'], s)} on MRP!")
    if bill.kind == "bill_of_supply":
        center("Composition dealer: GST not collected")
    center("Thank you! Visit again.")

    line_height = 11
    height = len(rows) * line_height + 40
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    pen = Pen(c, "Courier")
    y = height - 22
    for r in rows:
        for x, text, align, bold in r:
            pen.text(x, y, text, 9 if bold and len(r) == 1 else 8, bold, align)
        y -= line_height
    c.showPage()
    c.save()
    return buf.getvalue()


def scan(pdf: bytes, seed: str, receipt: bool) -> bytes:
    """Make a picture of the printed page: slight tilt, grain, blur, background, JPEG."""
    rng = random.Random(seed)
    page = pdfium.PdfDocument(pdf)[0]
    img = page.render(scale=(200 if receipt else 140) / 72).to_pil().convert("L")
    if receipt:  # a receipt photographed on a table
        table = Image.new("L", (img.width + 160, img.height + 160), 105)
        table.paste(ImageEnhance.Brightness(img).enhance(0.93), (80, 80))
        img = table
    img = img.rotate(rng.uniform(-2.5, 2.5), resample=Image.Resampling.BICUBIC, expand=True,
                     fillcolor=105 if receipt else 235)
    grain = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height)).point(lambda v: v // 10)
    img = ImageChops.subtract(img, grain)
    img = ImageEnhance.Contrast(img.filter(ImageFilter.GaussianBlur(0.7))).enhance(0.85)
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=72)
    return out.getvalue()


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    KEYS.mkdir(parents=True, exist_ok=True)
    for bill in BILLS:
        printed = make_printed(bill)
        pdf = (render_a4 if bill.layout == "a4" else render_receipt)(bill, printed)
        if bill.output == "scan":
            (DOCS / f"{bill.doc_id}.jpg").write_bytes(scan(pdf, f"{SEED}:{bill.doc_id}:scan", bill.layout == "receipt"))
        else:
            (DOCS / f"{bill.doc_id}.pdf").write_bytes(pdf)
        key = answer_key(bill, printed)
        (KEYS / f"{bill.doc_id}.json").write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n")
        print(f"{bill.doc_id}  {bill.kind:<15} {bill.layout:<8} {bill.output:<5} total {key['total']:>12,.2f}"
              f"  {key['expected_status']}")
    print(f"\n{len(BILLS)} bills written to {DOCS}/ and {KEYS}/")


if __name__ == "__main__":
    main()
