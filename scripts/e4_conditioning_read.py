#!/usr/bin/env python3
"""Run the prebuilt one-shot E4 conditioning read."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
_SRC=Path(__file__).resolve().parent.parent/"src"
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from meeting_minutes_agent.probes.e4_conditioning import load_manifest  # noqa:E402
from meeting_minutes_agent.probes.e4_conditioning_scoring import build_verdict,load_scores,render_report  # noqa:E402
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--manifest",required=True); p.add_argument("--responses",required=True); p.add_argument("--verdict-out",required=True); p.add_argument("--report-out",required=True); a=p.parse_args(argv)
 vo,ro=Path(a.verdict_out),Path(a.report_out)
 if vo.exists() or ro.exists(): p.error("one-shot outputs exist; refusing overwrite")
 v=build_verdict(load_manifest(a.manifest),load_scores(load_manifest(a.manifest),a.responses)); vo.parent.mkdir(parents=True,exist_ok=False); vo.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); ro.write_text(render_report(v),encoding="utf-8"); print(json.dumps({"decision":v["decision"],"verdict":str(vo),"report":str(ro)})); return 0
if __name__=="__main__": raise SystemExit(main())
