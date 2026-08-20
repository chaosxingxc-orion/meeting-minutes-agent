import json
from pathlib import Path

OUT = Path("/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent/docs/checks/2026-08-19-g1-floors-read")
v = json.loads((OUT / "verdict.json").read_text(encoding="utf-8"))
s = json.loads((OUT / "supplement.json").read_text(encoding="utf-8"))
arms = ["Z-turn", "Z-oracle", "Z-free", "Z-nodiar"]
meetings = v["meetings"]


def f(x, n=4):
    return "n/a" if x is None else f"{x:.{n}f}"


print("=== POOLED PER ARM ===")
print(f"{'arm':10s} {'cpWER':>8s} {'2ndConf':>9s} {'1stConf':>9s} {'gram':>7s} {'slices':>7s} {'refEmpty':>9s} {'orcRef':>7s} {'capped':>7s}")
for a in arms:
    p = v["pooled_by_arm"][a]
    print(f"{a:10s} {f(p['mean_cp_wer']):>8s} {f(p['mean_secondary_confusion_cost']):>9s} "
          f"{f(p['mean_primary_confusion_cost']):>9s} {f(p['mean_grammar_compliance']):>7s} "
          f"{p['total_slices']:>7d} {p['total_reference_empty']:>9d} {p['total_confusion_refused']:>7d} {p['total_capped_replies']:>7d}")

print()
print("=== PER MEETING cpWER ===")
print(f"{'meeting':9s} " + " ".join(f"{a:>9s}" for a in arms) + "   nsl(turn/oracle/free/nodiar)")
for m in meetings:
    row = []
    ns = []
    for a in arms:
        pm = v["pooled_by_arm"][a]["per_meeting"][m]
        row.append(f(pm["mean_cp_wer"]))
        ns.append(str(pm["n_slices"]))
    print(f"{m:9s} " + " ".join(f"{x:>9s}" for x in row) + "   " + "/".join(ns))

print()
print("=== PER MEETING primary confusion (tcpWER - tcORC@5s) : turn / oracle ===")
for m in meetings:
    t = v["pooled_by_arm"]["Z-turn"]["per_meeting"][m]
    o = v["pooled_by_arm"]["Z-oracle"]["per_meeting"][m]
    print(f"{m:9s} turn={f(t['mean_primary_confusion_cost'])} (n={t['n_primary_computable']}/{t['n_slices']})"
          f"   oracle={f(o['mean_primary_confusion_cost'])} (n={o['n_primary_computable']}/{o['n_slices']})")

print()
print("=== PER MEETING secondary confusion + grammar : turn / oracle / free / nodiar ===")
for m in meetings:
    parts = []
    for a in arms:
        pm = v["pooled_by_arm"][a]["per_meeting"][m]
        parts.append(f"{a}={f(pm['mean_secondary_confusion_cost'])}/g{f(pm['mean_grammar_compliance'],3)}")
    print(f"{m:9s} " + "  ".join(parts))

print()
print("=== ORC refusals + reference-empty slices (per arm, per meeting) ===")
for a in arms:
    for m in meetings:
        pm = v["pooled_by_arm"][a]["per_meeting"][m]
        if pm["n_confusion_refused"] or pm["n_reference_empty"]:
            reasons = sorted({sl["orc_refusal"][:70] for sl in pm["slices"] if sl["orc_refusal"]})
            print(f"  {a:9s} {m:9s} orc_refused={pm['n_confusion_refused']} ref_empty={pm['n_reference_empty']} "
                  f"n_slices={pm['n_slices']} :: {reasons if reasons else ''}")

print()
print("=== deployment gap meetings ===")
print("paired:", v.get("deployment_gap_meetings"))
print("dropped:", v.get("deployment_gap_meetings_dropped"))

print()
print("=== QA per meeting (macro F1) turn / oracle ===")
qt = s["qa"]["by_arm"]["Z-turn"]["per_meeting"]
qo = s["qa"]["by_arm"]["Z-oracle"]["per_meeting"]
for m in sorted(qt):
    print(f"  {m:9s} n={qt[m]['n']:3d}  turn F1={qt[m]['macro_f1']:.4f} EM={qt[m]['macro_em']:.4f}   "
          f"oracle F1={qo[m]['macro_f1']:.4f} EM={qo[m]['macro_em']:.4f}")
print("  unanswerable in cap:", s["qa"]["n_unanswerable_in_cap"])

print()
print("=== SAER-M detail ===")
print("scoreable:", s["saer_m"]["scoreable_meetings"])
print("unscoreable:", s["saer_m"]["unscoreable_meetings"])
for a in ["Z-turn", "Z-oracle"]:
    pm = s["saer_m"]["by_arm"][a]["per_meeting"]
    tot_b = sum(e.get("n_bullets", 0) for e in pm.values())
    tot_claims = sum(e.get("n_bullets_with_speaker_claim", 0) for e in pm.values())
    gold = sum(e.get("n_gold_sentence_ids", 0) for e in pm.values() if e.get("scoreable"))
    scored = sum(e.get("n_scored", 0) for e in pm.values() if e.get("scoreable"))
    corr = sum(e.get("n_correct", 0) for e in pm.values() if e.get("scoreable"))
    unatt = sum(e.get("n_unattributed", 0) for e in pm.values() if e.get("scoreable"))
    hall = sum(e.get("n_hallucinated_speaker", 0) for e in pm.values() if e.get("scoreable"))
    wrong = sum(e.get("n_wrong_speaker", 0) for e in pm.values() if e.get("scoreable"))
    ex = next(iter(pm.values()))
    print(f"  {a}: bullets={tot_b} with_speaker_claim={tot_claims} gold_sent_ids={gold} "
          f"n_scored={scored} correct={corr} wrong={wrong} unattributed={unatt} hallucinated={hall}")
    print(f"     example gold id={ex.get('example_gold_sentence_id')!r} predicted id={ex.get('example_predicted_sentence_id')!r}")
    print(f"     parse modes={s['saer_m']['by_arm'][a]['parse_modes']}")
    failed = [m for m, e in pm.items() if e.get("parse_mode") == "failed"]
    print(f"     failed-parse meetings: {failed}")
