# Data sources

DocSnap is tested on two kinds of Indian invoices:

1. **Generated invoices** (20): made by our own script, so the correct answers are known exactly.
2. **Real invoices** (10, listed below): published on the public web by the institutions that received them.

## Generated invoices

[`scripts/make_sample_invoices.py`](../scripts/make_sample_invoices.py) draws 20 bills and writes each answer key from the same numbers, so the keys are correct by construction. Every run makes identical files. Names, addresses and GSTINs are made up; any match with a real business is accidental.

```bash
uv run python scripts/make_sample_invoices.py
```

| Kind | Bills | What it tests |
|---|---|---|
| GST tax invoice, same state (CGST + SGST) | gen_01–03, gen_16 | Two GST rates, discount before tax, a service invoice, Tally-style tax table |
| GST tax invoice, other state (IGST) | gen_04–06, gen_17 | Taxed freight, totals in lakhs, an old balance printed under the total |
| Shop bill, prices include GST (MRP) | gen_07–09, gen_19 | GST shown inside the price, a "You saved" line |
| Restaurant bill | gen_10–13, gen_18, gen_20 | Service charge with GST on it, discount, round-off |
| Bill of supply (no GST) | gen_14–15 | No tax printed |

Eight are pictures of printed pages (tilted, grainy JPEGs); the rest are digital PDFs. Five carry one deliberate mistake each and should come out as "needs review": a wrong total (gen_16), an item amount with two digits swapped (gen_17), a malformed GSTIN (gen_18), the impossible date 31/04/2025 (gen_19), and a service charge left out of the total (gen_20).

## Real invoices

Indian colleges publish supporting documents for their NAAC accreditation, and these include copies of real vendor invoices, such as computers, internet and software. Each one below is a business-to-institution GST invoice that the institution published on its own website.

**These files are not stored in this repository.** Copyright stays with the publishers, and the documents name real businesses. A script downloads each file from its original link, checks it against the checksum in [`real_sources.json`](real_sources.json), and keeps only the listed page(s):

```bash
uv run python scripts/fetch_real_invoices.py
```
The answer key holds only the values printed on those pages. Each key was read twice, with close-ups for unclear values, and its sums are tested. A value that cannot be read for certain is left unscored rather than guessed.

| ID | Published by | Seller → buyer state | Tax | Kind | Page(s) | Link |
|---|---|---|---|---|---|---|
| real_01 | Kakatiya Institute of Technology & Science, Warangal | Telangana → Telangana | CGST + SGST | Scan, highlighter marks | 2 | [PDF](https://kitsw.ac.in/NAAC/Clarifications_of_Criterion/4.3.2/4.3.2(2)_Bills/4.3.2_MED_Computer%20bills.pdf) |
| real_02 | SPDT College, Mumbai | Maharashtra → Maharashtra | CGST + SGST | Phone photo, stamps, transport charge | 1 | [PDF](https://www.spdtcollege.ac.in/uploads/DVVCREATION-VII/7-1-2.pdf) |
| real_03 | Velammal College of Engineering & Technology, Madurai | Tamil Nadu → Tamil Nadu | CGST + SGST | Digital telecom bill, 2 pages | 1–2 | [PDF](https://vcet.ac.in/vcetit/pdfs/NAAC/AQAR/2022-2023/Criteria-4/4.3.1.pdf) |
| real_04 | Axis Institute of Higher Education, Kanpur | Uttar Pradesh → Uttar Pradesh | CGST + SGST | Scan, ~20 line items over 2 pages | 1–2 | [PDF](https://aihe.ac.in/upload/naac/1723894071.pdf) |
| real_05 | R. R. Mehta College of Science & C. L. Parikh College of Commerce, Palanpur | Gujarat → Gujarat | CGST + SGST | Scan, tilted, handwriting on the page | 2 | [PDF](https://rrmcsclpcc.ac.in/admin/assets-admin/naac-pdf/413_NPS_Brodband.pdf) |
| real_06 | Sant Baba Bhag Singh University, Jalandhar | Punjab → Punjab | CGST + SGST | Digital broadband bill | 1 | [PDF](https://sbbsuniversity.ac.in/iqac/pdf/4.3.4(%20internet%20Speed).pdf) |
| real_07 | AAA College of Engineering & Technology, Sivakasi | Tamil Nadu → Tamil Nadu | CGST + SGST | Digital, clean layout | 1 | [PDF](https://aaaenggcoll.ac.in/wp-content/uploads/2026/01/11-Proof-of-Internet-Bandwidth-2026.pdf) |
| real_08 | Bhavan's Vivekananda College, Secunderabad | Telangana → Telangana | CGST + SGST | Scan, amount in lakhs | 2 | [PDF](https://bhavansvc.ac.in/NAAC/criteria/Criteria%207/7.1.2/Additional%20Information.pdf) |
| real_09 | Bhavan's Vivekananda College, Secunderabad | Maharashtra → Telangana | IGST | Scan, interstate | 2 | [PDF](https://bhavansvc.ac.in/NAAC/criteria/Criteria%206/6.2.3/ERP%20Bills.pdf) |
| real_10 | Biju Patnaik Institute of IT & Management, Bhubaneswar | Maharashtra → Odisha | IGST | Digital software invoice, 2 pages | 1–2 | [PDF](https://www.biitm.ac.in/naac_documents/1949611686_ilovepdf_merged%20(19).pdf) |

Links were checked on 30 October 2026.

## Searched, not used

- **Wikimedia Commons** has only a few Indian bills, and they are blank or handwritten.
- **Public invoice datasets** (CORD, SROIE, FATURA) are not Indian. They are kept for a later version.
- **No public, labelled dataset of Indian invoices** was found ([request on the Hugging Face forum](https://discuss.huggingface.co/t/seeking-indic-document-dataset-india-invoices-receipts-utility-bills-payment-advices-packing-lists-commercial-invoices-credit-notes/177055)).
