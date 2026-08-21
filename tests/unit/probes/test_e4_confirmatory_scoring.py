from __future__ import annotations
from meeting_minutes_agent.probes.e4_confirmatory import RuntimeBinding,RuntimeTarget,ScoreBinding,ScoreTarget
from meeting_minutes_agent.probes.e4_confirmatory_scoring import CFScore,build_verdict
def test_directional_rule_does_not_claim_confirmation_below_five_points():
 targets=tuple(RuntimeTarget(f"D{i}-turn000",f"D{i}",0,"speaker_1",0,1,("g",),("s",),("w",),"x","y","0"*64) for i in range(100));score_targets=tuple(ScoreTarget(x.target_id,x.uniq_id,"term",("term",)) for x in targets);scores=[]
 for i,t in enumerate(targets):
  for arm in ("CF0-bare","CF1-global","CF2-speaker","CF3-wrong"):
   limit={"CF0-bare":94,"CF1-global":94,"CF2-speaker":96,"CF3-wrong":92}[arm];hit=int(i<limit);carry_error=1-hit
   scores.append(CFScore(t.target_id,t.uniq_id,arm,1,10,carry_error,1,hit,1,0,10))
 v=build_verdict(RuntimeBinding({"content_hash":"r"},targets),ScoreBinding({"content_hash":"s"},score_targets),scores)
 assert v["decision"]!="SPEAKER-CONDITIONING-CONFIRMED"
