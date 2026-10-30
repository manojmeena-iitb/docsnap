# DocSnap — spec (v0.1)

## Problem
Freelancers, shops and small businesses type invoice and receipt details into Excel by hand. It is slow and full of typos. DocSnap reads the file, fills the row, checks its own work and says how accurate it is.

## Users
Anyone who handles bills: a freelancer doing monthly expenses, a shop owner, a small-business accountant.

## Input
- One file or a folder of files: PDF, JPG, PNG.
- Invoices and receipts in English, printed (not handwritten).

## Output
For each file, these fields:

| Field | Type | Example |
|---|---|---|
| `vendor_name` | text | "Sharma Traders" |
| `invoice_number` | text or empty | "INV-2041" |
| `invoice_date` | date (YYYY-MM-DD) | 2026-10-12 |
| `currency` | 3-letter code | "INR" |
| `line_items` | list of {description, quantity, unit_price, amount} | — |
| `subtotal` | number | 1200.00 |
| `tax` | number | 216.00 |
| `total` | number | 1416.00 |
| `vendor_gstin` | text or empty | "27ABCDE1234F1Z5" |
| `status` | "ok" or "needs_review" | "ok" |
| `problems` | list of text | ["total does not match"] |

Saved as one JSON file per document, plus one row per document added to a CSV file.

## Checks (after the AI reads the file)
1. Line-item amounts add up to the subtotal (within ₹1 for rounding).
2. Subtotal + tax = total (within ₹1).
3. The date is a real date and not in the future.
4. The GSTIN, if present, has the right format (15 characters, set pattern).

If any check fails: ask the AI once more, telling it what failed. If it still fails: keep the result, set `status = "needs_review"` and list the problems. Never hide a failure.

## How it reads files
- PDF with real text inside → read the text, send it to the AI.
- Photo or scanned PDF → send the image to the AI (vision).
- The AI must answer in the exact field format above (structured output, checked with Pydantic).

## How to use it
- Command line: `docsnap extract bill.pdf` and `docsnap extract bills/ --csv out.csv`
- Web page (Streamlit): drag a file in → see the fields → download the CSV.

## Accuracy report (evals)
- Test set: 30 documents with hand-written correct answers ("ground truth").
  - 15 made by a script (different layouts, some with mistakes on purpose)
  - 10 real receipts (in `data/private/`, never on GitHub)
  - 5 free public sample invoices
- Report: accuracy per field, % of documents fully correct, % flagged "needs review", cost per document, time per document.
- Compare at least two setups (e.g. a cheaper model vs a stronger one).
- Group every error by cause (failure analysis).

## Not in v0.1
Login, cloud hosting, a database, other languages, handwritten bills, editing results in the web page.

## Done means
- Public GitHub repo with tests passing automatically (GitHub Actions).
- Accuracy report with real numbers in the README.
- README a recruiter understands in 90 seconds, with a demo GIF.
- Release v0.1 and one LinkedIn post.
