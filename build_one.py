# -*- coding: utf-8 -*-
"""Generic builder: python3 build_one.py <module> "<Output Name>.docx"
The module must expose PASSAGES = [ {num,title,paragraphs,entries}, ... ].
"""
import sys, re, importlib
import docx_builder as db

def validate(passages):
    problems = []
    for p in passages:
        full = " ".join(p["paragraphs"]).lower()
        for e in p["entries"]:
            ok = False
            for hl in e["hl"]:
                pat = re.compile(r"(?<![a-z])" + re.escape(hl.lower()).replace(r"\ ", r"\s+") + r"(?![a-z])")
                if pat.search(full):
                    ok = True; break
            if not ok:
                problems.append((p["num"], e["word"], e["hl"]))
    return problems

if __name__ == "__main__":
    mod = importlib.import_module(sys.argv[1])
    out_name = sys.argv[2]
    passages = mod.PASSAGES
    probs = validate(passages)
    if probs:
        print("UNMATCHED (%d):" % len(probs))
        for num, word, hl in probs:
            print("  P%d  %-22s hl=%s" % (num, word, hl))
    else:
        print("All highlight terms matched.")
    for p in passages:
        print("Passage %d: %d entries" % (p["num"], len(p["entries"])))
    db.write_docx(passages, out_name)
    print("Wrote:", out_name)
