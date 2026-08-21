#!/usr/bin/env python3
"""Build leakage-separated four-arm bindings after confirmatory Pass 0."""
from __future__ import annotations
import argparse,hashlib,json,math,sys
from pathlib import Path
_SRC=Path(__file__).resolve().parent.parent/"src"
if str(_SRC) not in sys.path:sys.path.insert(0,str(_SRC))
from meeting_minutes_agent.glossary.arms import gated_arm  # noqa:E402
from meeting_minutes_agent.glossary.gate import GateConfig  # noqa:E402
from meeting_minutes_agent.probes.e4_confirmatory import load_pass0_runtime,load_pass0_score  # noqa:E402
from meeting_minutes_agent.probes.state_audit import contains_entity  # noqa:E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa:E402
def _terms(text):return tuple(x.canonical_surface for x in gated_arm(text,chunk_index=0,gate_config=GateConfig(min_evidence=1,inventory_cap=8)).entries)
def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--runtime-manifest",required=True);p.add_argument("--score-manifest",required=True);p.add_argument("--responses",required=True);p.add_argument("--runtime-out",required=True);p.add_argument("--score-out",required=True);p.add_argument("--summary-out",required=True);p.add_argument("--min-carry",type=int,default=707);a=p.parse_args(argv)
 outputs=[Path(a.runtime_out),Path(a.score_out),Path(a.summary_out)]
 if any(x.exists() for x in outputs):p.error("output exists; refusing overwrite")
 runtime=load_pass0_runtime(a.runtime_manifest);score=load_pass0_score(a.score_manifest);score_by={e.uniq_id:e for e in score.entries};hyp={}
 for line in Path(a.responses).read_text(encoding="utf-8").splitlines():
  r=json.loads(line)
  if r.get("outcome")=="ok":hyp.setdefault(str(r["uniq_id"]),{})[int(r["turn_index"])]=str(r["text"])
 missing=sum(len(e.turns)-len(hyp.get(e.uniq_id,{})) for e in runtime.entries)
 if missing:raise ValueError(f"Pass0 incomplete: {missing} turns missing")
 runtime_targets=[];score_targets=[];total_carry=usable_carry=total_targets=dropped_targets=0
 for entry in runtime.entries:
  se=score_by[entry.uniq_id];st_by={t.index:t for t in se.turns}
  for turn in entry.turns[1:]:
   st=st_by[turn.index];carry=tuple(entity for entity in se.entity_list if contains_entity(st.reference_text,entity) and any(x.speaker_id==turn.speaker_id and contains_entity(st_by[x.index].reference_text,entity) for x in entry.turns[:turn.index]))
   if not carry:continue
   total_targets+=1;total_carry+=len(carry);prior=entry.turns[:turn.index];same=" ".join(hyp[entry.uniq_id][x.index] for x in prior if x.speaker_id==turn.speaker_id);glob=" ".join(hyp[entry.uniq_id][x.index] for x in prior);wrong=" ".join(hyp[entry.uniq_id][x.index] for x in prior if x.speaker_id!=turn.speaker_id);s,g,w=_terms(same),_terms(glob),_terms(wrong);width=min(len(s),len(g),len(w))
   if width<1:dropped_targets+=1;continue
   target_id=f"{entry.uniq_id}-turn{turn.index:03d}";usable_carry+=len(carry);runtime_targets.append({"target_id":target_id,"uniq_id":entry.uniq_id,"turn_index":turn.index,"speaker_id":turn.speaker_id,"start":turn.start,"end":turn.end,"global_terms":list(g[:width]),"speaker_terms":list(s[:width]),"wrong_terms":list(w[:width]),"source_tar":entry.source_tar,"tar_member":entry.tar_member,"audio_sha256":entry.audio_sha256});score_targets.append({"target_id":target_id,"uniq_id":entry.uniq_id,"reference_text":st.reference_text,"carry_entities":list(carry)})
 summary={"schema_version":"e4-cf-binding-summary-v1","total_targets":total_targets,"usable_targets":len(runtime_targets),"dropped_targets":dropped_targets,"total_carry_mentions":total_carry,"usable_carry_mentions":usable_carry,"min_carry":a.min_carry,"usable_fraction":usable_carry/total_carry,"decision":"ATTRITION-GATE-PASS" if usable_carry>=a.min_carry else "UNDERPOWERED-ATTRITION","second_pass_calls":len(runtime_targets)*4,"second_pass_audio_seconds":sum((x["end"]-x["start"])*4 for x in runtime_targets)}
 outputs[2].parent.mkdir(parents=True,exist_ok=False);outputs[2].write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
 if usable_carry<a.min_carry:print(json.dumps(summary));return 2
 common={"experiment_id":"E4-CF-287-v1","pass0_responses_sha256":_sha(Path(a.responses)),"binding_summary":str(a.summary_out)};rt={"schema_version":"e4-cf-runtime-binding-v1",**common,"targets":runtime_targets};rt["content_hash"]=config_hash(rt);sc={"schema_version":"e4-cf-score-binding-v1",**common,"targets":score_targets};sc["content_hash"]=config_hash(sc);outputs[0].parent.mkdir(parents=True,exist_ok=True);outputs[0].write_text(json.dumps(rt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");outputs[1].write_text(json.dumps(sc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({**summary,"runtime_hash":rt["content_hash"],"score_hash":sc["content_hash"]}));return 0
if __name__=="__main__":raise SystemExit(main())
