# -*- coding: utf-8 -*-
import re
import docx_builder as db
import passage1, passage2, passage3

PASSAGES = [
    {"num": 1, "title": "Why do people collect things?",
     "paragraphs": passage1.PARAGRAPHS, "entries": passage1.ENTRIES},
    {"num": 2, "title": "Making Documentary Films",
     "paragraphs": passage2.PARAGRAPHS, "entries": passage2.ENTRIES},
    {"num": 3, "title": "Jellyfish: A Remarkable Marine Life Form",
     "paragraphs": passage3.PARAGRAPHS, "entries": passage3.ENTRIES},
]

# ---- validation: ensure every highlight term appears in its passage ----
def validate():
    problems = []
    for p in PASSAGES:
        full = " ".join(p["paragraphs"]).lower()
        for e in p["entries"]:
            found_any = False
            for hl in e["hl"]:
                pat = re.compile(r"(?<![a-z])" + re.escape(hl.lower()).replace(r"\ ", r"\s+") + r"(?![a-z])")
                if pat.search(full):
                    found_any = True
                    break
            if not found_any:
                problems.append((p["num"], e["word"], e["hl"]))
    return problems

if __name__ == "__main__":
    probs = validate()
    if probs:
        print("UNMATCHED ENTRIES (%d):" % len(probs))
        for num, word, hl in probs:
            print("  P%d  %-22s  hl=%s" % (num, word, hl))
    else:
        print("All highlight terms matched their passages.")
    for p in PASSAGES:
        print("Passage %d: %d vocab entries" % (p["num"], len(p["entries"])))
    out = db.write_docx(PASSAGES, "Boost Your Vocabulary - Test 1 Reading.docx")
    print("Wrote:", out)
