"""Build a local review page: each eval document beside its ground-truth answers.

A person checks every answer against the document before it is used for scoring.
Writes data/eval/review.html (not in git). Open it in a browser:
  uv run python scripts/review_ground_truth.py && open data/eval/review.html
"""

import html
import json
from pathlib import Path

EVAL = Path("data/eval")
FIELDS = ["vendor_name", "invoice_number", "invoice_date", "currency", "subtotal",
          "discount", "service_charge", "tax", "total", "vendor_gstin", "expected_status"]


def show(value) -> str:
    """Format one answer for display; empty means 'not on the document'."""
    if value is None:
        return '<span class="empty">— not on document</span>'
    if isinstance(value, float):
        return indian_number(value)
    return html.escape(str(value))


def indian_number(value: float) -> str:
    """Group digits the Indian way, as printed on the bills: 15,57,857.14."""
    sign = "-" if value < 0 else ""
    whole, paise = f"{abs(value):.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups + [tail]) + "." + paise


def preview(doc_path: Path) -> str:
    """Show a PDF in a scrollable frame, an image as a picture."""
    src = f"docs/{doc_path.name}"
    if doc_path.suffix.lower() == ".pdf":
        return f'<iframe src="{src}" title="{doc_path.stem}"></iframe>'
    return f'<a href="{src}" target="_blank"><img src="{src}" loading="lazy"></a>'


def doc_card(doc_path: Path, truth: dict) -> str:
    """HTML for one document: image on the left, answers on the right."""
    doc_id = doc_path.stem
    meta = truth.get("_meta", {})
    unlabelled = set(meta.get("not_labelled", []))
    rows = "".join(
        f"<tr><th>{f}</th><td>{'<span class=empty>not scored (unreadable or not labelled)</span>' if f in unlabelled else show(truth.get(f))}</td></tr>"
        for f in FIELDS
    )
    items = truth.get("line_items") or []
    item_rows = "".join(
        f"<tr><td>{show(i.get('description'))}</td><td>{show(i.get('quantity'))}</td>"
        f"<td>{show(i.get('unit_price'))}</td><td>{show(i.get('amount'))}</td></tr>"
        for i in items
    ) or '<tr><td colspan="4" class="empty">no line items</td></tr>'
    checked = "done" if meta.get("checked_by_hand") else ""
    return f"""
<section class="card {checked}" id="{doc_id}">
  <div class="img">{preview(doc_path)}
    <p class="hint"><a href="docs/{doc_path.name}" target="_blank">Open the document full size</a></p></div>
  <div class="answers">
    <h2>{doc_id}</h2>
    <p class="src">{html.escape(meta.get('source', ''))} · {html.escape(meta.get('licence', ''))}</p>
    <table class="fields">{rows}</table>
    <h3>Line items</h3>
    <table class="items"><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Amount</th></tr>{item_rows}</table>
    <p class="note"><b>Draft note:</b> {html.escape(meta.get('draft_note', meta.get('note', '')))}</p>
    <p class="src">{html.escape(meta.get('review', ''))}</p>
    {'<p class="ok">Already checked by hand.</p>' if checked else ''}
    <div class="verdict" data-doc="{doc_id}">
      <label><input type="radio" name="v_{doc_id}" value="OK"> All correct</label>
      <label><input type="radio" name="v_{doc_id}" value="FIX"> Needs a fix</label>
      <textarea placeholder="What should change? e.g. total should be 31,500"></textarea>
    </div>
  </div>
</section>"""


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>DocSnap ground-truth review</title>
<style>
body{{font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;background:#f5f5f4;color:#1c1917}}
header{{position:sticky;top:0;background:#1c1917;color:#fff;padding:12px 20px;display:flex;gap:16px;align-items:center;z-index:2}}
header button{{font:inherit;padding:6px 14px;border-radius:6px;border:0;background:#fbbf24;cursor:pointer}}
main{{max-width:1300px;margin:auto;padding:16px}}
.card{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;background:#fff;border-radius:10px;padding:16px;margin:16px 0;box-shadow:0 1px 3px #0002}}
.card.done{{opacity:.6}}
.img img{{width:100%;max-height:900px;object-fit:contain;border:1px solid #ddd}}
.img iframe{{width:100%;height:900px;border:1px solid #ddd}}
h2{{margin:0;font-size:18px}} h3{{margin:14px 0 6px;font-size:15px}}
.src,.hint{{color:#78716c;font-size:13px;margin:4px 0 10px}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #e7e5e4;padding:4px 6px;text-align:left;vertical-align:top}}
.fields th{{width:38%;color:#57534e;font-weight:500}}
.empty{{color:#a8a29e;font-style:italic}}
.note{{background:#fef3c7;padding:8px;border-radius:6px}} .ok{{color:#15803d;font-weight:600}}
.verdict{{margin-top:10px;display:flex;flex-wrap:wrap;gap:12px}} textarea{{width:100%;min-height:50px;font:inherit}}
@media(max-width:800px){{.card{{grid-template-columns:1fr}}}}
</style></head><body>
<header><b>DocSnap · ground-truth review</b><span id="count"></span><button id="copy">Copy my review</button><span id="msg"></span></header>
<main>
<p>For each document: compare every answer with the document. Empty means "not printed on the document". Dates are YYYY-MM-DD. Tax is the sum of all tax parts (CGST + SGST, or IGST). Read the yellow note first: it explains any judgement call.</p>
{cards}
</main>
<script>
const KEY='docsnap-review';
let state={{}}; try{{state=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
const save=()=>{{try{{localStorage.setItem(KEY,JSON.stringify(state))}}catch(e){{}}; count()}};
const boxes=[...document.querySelectorAll('.verdict')];
function count(){{const n=boxes.filter(b=>state[b.dataset.doc]?.v).length;document.getElementById('count').textContent=n+' / '+boxes.length+' reviewed'}}
boxes.forEach(b=>{{const d=b.dataset.doc,s=state[d]||{{}};
  b.querySelectorAll('input').forEach(i=>{{if(i.value===s.v)i.checked=true;i.onchange=()=>{{state[d]={{...state[d],v:i.value}};save()}}}});
  const t=b.querySelector('textarea');t.value=s.t||'';t.oninput=()=>{{state[d]={{...state[d],t:t.value}};save()}};}});
document.getElementById('copy').onclick=async()=>{{
  const text=boxes.map(b=>{{const s=state[b.dataset.doc]||{{}};return b.dataset.doc+': '+(s.v||'NOT REVIEWED')+(s.t?' - '+s.t:'')}}).join('\\n');
  try{{await navigator.clipboard.writeText(text);document.getElementById('msg').textContent='Copied — paste it in chat.'}}
  catch(e){{prompt('Copy this text:',text)}}}};
count();
</script></body></html>"""


def main() -> None:
    cards = []
    for doc_path in sorted((EVAL / "docs").iterdir()):
        truth_path = EVAL / "ground_truth" / f"{doc_path.stem}.json"
        if truth_path.exists():
            cards.append(doc_card(doc_path, json.loads(truth_path.read_text())))
    (EVAL / "review.html").write_text(PAGE.format(cards="".join(cards)))
    print(f"Wrote {EVAL / 'review.html'} with {len(cards)} documents")


if __name__ == "__main__":
    main()
