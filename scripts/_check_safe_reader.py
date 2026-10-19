import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import safe_reader

for p in sorted((pathlib.Path('data/practice_docs')).iterdir()):
    if p.suffix.lower() not in safe_reader.SUPPORTED_SUFFIXES:
        continue
    d = safe_reader.read_safely(p)
    print(f"{p.name:<30} visible={len(d.visible_text):>5}  quarantined={len(d.quarantined)}")
    for q in d.quarantined:
        print(f"      - [{q.location}] {q.reason}")
        print(f"        {q.text[:95]}")
