# What can break — and what DocSnap does about it

Every build step is checked for ways it can fail. Each risk gets a status:
**handled** (code + test), **planned** (day it will be handled), or **accepted** (known limit, stated in the README).

| # | Step | What can break | Impact | Status |
|---|---|---|---|---|
| 1 | Reading photos | Phone photos can be 5–8 MB; the AI API rejects images over ~5 MB | Extraction fails on real photos | Planned (Day 5): shrink images before sending |
| 2 | Total check | Bills with discounts or service charges fail a plain "subtotal + tax = total" check | Correct bills wrongly flagged | Handled in spec: discount and service charge are fields; check uses both |
| 3 | Total check | Some bills print prices that already include tax (MRP-style retail bills) | Correct bills wrongly flagged | Handled in spec: "tax included" formula also accepted |
| 4 | Total check | GST is charged on the service charge too (tax base = subtotal + service charge) | A rate-based check would wrongly flag correct restaurant bills | Handled in spec: the check adds up the printed amounts; it never recomputes tax from a rate |
| 5 | Eval data | Source labels can be wrong or incomplete | Accuracy numbers would be wrong | Handled: every key is read twice against the document, with close-ups for unclear values; sums are tested (#22). A person's check is recorded separately (`checked_by_hand`) |
| 6 | Field format | Invoice numbers come with prefixes ("Invoice No: GST/24-25/017"); dates come in many formats (18-05-2024, 18 May 2024) | Correct answers scored as wrong | Planned (Day 4/9): store clean values; compare dates after converting to YYYY-MM-DD |
| 7 | Amounts | Indian bills write 1,00,000 (lakh grouping); "Rs.", "₹" and "INR" all appear | Amounts misread | Planned (Day 4/6): parse to plain numbers; sanity checks on totals |
| 8 | Tax | Tax is split into CGST + SGST, or IGST, sometimes plus cess | Tax compared wrongly | Handled in spec: `tax` = sum of all tax parts |
| 9 | Scoring | Item names differ only in case or punctuation | Correct answers scored as wrong | Planned (Day 9): compare descriptions ignoring case, spaces and punctuation; amounts compared exactly |
| 10 | Item check | Item prices include tax while the printed subtotal is before tax | Correct bills wrongly flagged | Handled in spec: items may add up to the subtotal or to the total |
| 11 | Made-up values | The model fills a field that isn't printed (e.g. guesses a tax figure from a gap in the total) | Wrong data that looks right | Planned (Day 4/6): prompt + schema allow "empty"; eval counts invented values as errors |
| 12 | Personal data | Real invoices carry names, addresses, phone numbers | Privacy and legal risk if republished | Handled: web invoices are linked, not stored in the repo; private files stay in `data/private/` |
| 13 | Scope | Non-Indian bills and Hindi / other scripts | Unknown accuracy | Accepted for v0.1; planned for v0.2 |
| 14 | Reading PDFs | A scanned PDF can carry a poor OCR text layer (seen in the test set: "IGST@1aolo" for "IGST@18%"), so the text route reads garbage | Wrong values from a file that looks digital | Planned (Day 4/5): treat a PDF as digital only if its text passes sanity checks; otherwise send the page image |
| 15 | Reading PDFs | One invoice can span two pages, with items on page 1 and totals on page 2 | Missing totals or items | Planned (Day 5): send all pages of a document together; test set includes 2-page invoices |
| 16 | Eval data | Web links can break, or a file can change after the answer key was written | Eval can't run, or scores against the wrong file | Handled: `scripts/fetch_real_invoices.py` checks every file against its SHA-256 checksum in `data/real_sources.json` and names any link that is broken or changed (tested) |
| 17 | Total check | The printed tax rate can be rounded or wrong (seen: "0.03" printed for 2.5%) while the amounts are right | A rate-based check would flag a correct bill | Handled in spec: checks use printed amounts, never printed rates (see #4) |
| 18 | Eval data | A published page can be part of a longer invoice whose other pages were never published (seen: a page ending "continued…", no total) | A test case with no correct total | Handled: each chosen page was checked by hand to hold a complete invoice |
| 19 | Total check | Taxed extra charges (transport, freight) are printed below the items, outside the item list | The model drops them and the total check fails | Handled in spec: they count as line items; subtotal = the printed taxable value |
| 20 | Made-up values | Bills print other big numbers near the total: previous balance, annual charges, "invoice balance 0.00" | Wrong total that looks right | Planned (Day 4): prompt names these traps; real test set contains three of them |
| 21 | Field format | Dates can be month-first (12/16/2020 on a US-company invoice) or day-first (21-01-2022) | Day and month swapped | Planned (Day 4): ask for YYYY-MM-DD; the date check rejects impossible dates |
| 22 | Eval data | An answer key can carry a typo | Correct output scored as wrong | Handled: a test checks that every correct invoice's key adds up and has a valid date and GSTIN |
| 23 | Eval data | A scanned value can be too blurred to read for certain (seen: invoice number 036 / 035 / 636 / 635) | A guessed answer key would score a correct reading as wrong | Handled: the field is listed in `_meta.not_labelled` and not scored |
| 24 | Eval data | Generated bills are cleaner and more regular than real ones | Accuracy looks better than it is | Partly handled: scans get tilt, grain and blur. Planned (Day 9): report generated and real scores separately |
| 25 | Eval data | The generator makes different bills on another run | Answer keys stop matching the documents | Handled: a fixed seed per bill and PDFs without timestamps (two runs give identical files); a test rebuilds every key and compares it with the repo |
| 26 | Eval data | A planted mistake that the checks cannot actually catch | A bill marked "needs review" that a correct validator passes | Handled: a test runs the SPEC checks on every key; each mistake bill must fail one, each correct bill must pass all |
| 27 | Total check | The "prices include tax" rule also passes a bill that forgot to add tax (found by testing: 1,000 + 180 tax printed as total 1,000 is not flagged) | A wrong bill marked ok | Planned (Day 6): use the tax-included formula only when the bill says prices include GST |
| 28 | Eval data | The PDF fonts used have no ₹ sign, so generated bills print "Rs." only | ₹ is not tested on generated bills | Accepted: real bills in the test set print ₹ |
| 29 | Privacy | A made-up GSTIN has a valid check digit and could match a real business by chance | A real business named in made-up data | Accepted: seller names are made up, and SOURCES.md says any match is accidental |
