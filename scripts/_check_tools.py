import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import tools

for n in ["data/practice_docs/p01_bluehen_quote.html",
          "data/practice_docs/p05_maplemills_quote.pdf",
          "data/practice_docs/p08_chapelst_email.eml"]:
    p = tools.resolve_document_path(n)
    t = tools.extract_document_text(p)
    print(n, "->", len(t), "chars |", t.replace("\n", " / ")[:80])

for bad in ["../.env", "data/practice_docs/nope.txt", "data/prices.json"]:
    try:
        tools.resolve_document_path(bad)
        print("NOT BLOCKED:", bad)
    except tools.DocumentError as e:
        print("blocked:", bad, "->", str(e)[:70])
