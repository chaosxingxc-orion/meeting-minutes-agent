from __future__ import annotations
from meeting_minutes_agent.probes.e4_conditioning import E4Manifest,E4Target
from meeting_minutes_agent.probes.e4_conditioning_scoring import E4Score,build_verdict
def _manifest():
 t=E4Target("D1",2,"speaker_1",20,30,"Hydro Dent launched",("Hydro Dent",),"wrong",("Hydro Dent",),("Acme",),("Other",),("Hdyro Dnet",),"x","y","0"*64)
 return E4Manifest({"content_hash":"h"},(t,))
def _score(arm,hits=(),wer=1,carry=1): return E4Score("D1-turn002","D1",arm,wer,10,carry,2,tuple(hits),1,0,10)
def test_reachable_rule_is_mechanical_with_three_corrections():
 m=_manifest(); m=E4Manifest(m.raw,m.targets*3)
 # Distinct ids are not required by build_verdict; construct three score rows per arm with ids.
 scores=[]
 for arm in ("E4-0-bare","E4-1-label","E4-2-global","E4-3-speaker","E4-4-wrong","E4-5-corrupt"):
  for i in range(3):
   s=_score(arm,("Hydro Dent",) if arm=="E4-3-speaker" else (),wer=1,carry=0 if arm=="E4-3-speaker" else 1)
   scores.append(E4Score(f"T{i}-turn000",f"T{i}",s.arm,s.wer_errors,s.wer_tokens,s.carry_errors,s.carry_tokens,s.carry_hits,s.carry_total,0,10))
 targets=tuple(E4Target(f"T{i}",0,"speaker_1",0,1,"Hydro Dent",("Hydro Dent",),"",("x",),("y",),("z",),("q",),"x","y","0"*64) for i in range(3))
 v=build_verdict(E4Manifest({"content_hash":"h"},targets),scores)
 assert v["decision"]=="SPEAKER-CONDITIONING-REACHABLE"
