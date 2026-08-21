"""Dialogue-clustered one-shot scoring for E4 confirmatory."""
from __future__ import annotations
import json,random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping,Sequence
from .contextasr_scoring import normalize_english
from .e4_confirmatory import ARMS,RuntimeBinding,ScoreBinding
def _distance(a,b):
 import editdistance
 return int(editdistance.eval(list(a),list(b)))
def _contains(text,term):return f" {normalize_english(term)} " in f" {normalize_english(text)} "
def _entity_error(hyp,entity):
 target=normalize_english(entity).split();tokens=normalize_english(hyp).split();n=len(target);values=[]
 for start in range(len(tokens)):
  for size in range(max(1,n-1),n+2):
   if start+size<=len(tokens):values.append(_distance(target,tokens[start:start+size]))
 return min(values,default=n)
@dataclass(frozen=True)
class CFScore:
 target_id:str;uniq_id:str;arm:str;wer_errors:int;wer_tokens:int;carry_errors:int;carry_tokens:int;carry_hits:int;carry_total:int;false_hint_activations:int;completion_tokens:int
def load_scores(runtime:RuntimeBinding,score:ScoreBinding,responses:str|Path)->tuple[CFScore,...]:
 if {x.target_id for x in runtime.targets}!={x.target_id for x in score.targets}:raise ValueError("runtime/score target ids differ")
 records={}
 for line in Path(responses).read_text(encoding="utf-8").splitlines():
  r=json.loads(line)
  if r.get("outcome")=="ok":records[(str(r["target_id"]),str(r["arm"]))]=r
 expected={(x.target_id,a) for x in score.targets for a in ARMS};missing=expected-records.keys()
 if missing:raise ValueError(f"confirmatory read incomplete: {len(missing)} cells")
 score_by={x.target_id:x for x in score.targets};out=[]
 for target_id,arm in sorted(expected):
  target=score_by[target_id];r=records[(target_id,arm)];hyp=str(r["text"]);ref=normalize_english(target.reference_text).split();ht=normalize_english(hyp).split();terms=tuple(str(x) for x in r.get("injected_terms",()))
  out.append(CFScore(target_id,target.uniq_id,arm,_distance(ref,ht),len(ref),sum(_entity_error(hyp,e) for e in target.carry_entities),sum(len(normalize_english(e).split()) for e in target.carry_entities),sum(_contains(hyp,e) for e in target.carry_entities),len(target.carry_entities),sum(_contains(hyp,t) and not _contains(target.reference_text,t) for t in terms),int(dict(r.get("usage",{})).get("completion_tokens",0))))
 return tuple(out)
def _components(scores:Sequence[CFScore]):
 return {"wer_errors":sum(x.wer_errors for x in scores),"wer_tokens":sum(x.wer_tokens for x in scores),"carry_errors":sum(x.carry_errors for x in scores),"carry_tokens":sum(x.carry_tokens for x in scores),"carry_hits":sum(x.carry_hits for x in scores),"carry_total":sum(x.carry_total for x in scores),"false_hint_activations":sum(x.false_hint_activations for x in scores),"truncated":sum(x.completion_tokens>=512 for x in scores)}
def _metrics(c):return {**c,"wer":c["wer_errors"]/c["wer_tokens"],"carry_ne_wer":c["carry_errors"]/c["carry_tokens"],"carry_hit_rate":c["carry_hits"]/c["carry_total"],"carry_fnr":1-c["carry_hits"]/c["carry_total"]}
def _cluster_ci(scores, left, right, metric):
 grouped=defaultdict(lambda:defaultdict(list))
 for s in scores:grouped[s.uniq_id][s.arm].append(s)
 ids=sorted(grouped);rng=random.Random(20260820);values=[]
 for _ in range(10000):
  sample=[ids[rng.randrange(len(ids))] for _ in ids];lc=defaultdict(int);rc=defaultdict(int)
  for uid in sample:
   for k,v in _components(grouped[uid][left]).items():lc[k]+=v
   for k,v in _components(grouped[uid][right]).items():rc[k]+=v
  values.append(_metrics(lc)[metric]-_metrics(rc)[metric])
 values.sort();return {"low":values[249],"high":values[9749]}
def build_verdict(runtime:RuntimeBinding,score:ScoreBinding,scores:Sequence[CFScore]):
 grouped=defaultdict(list)
 for s in scores:grouped[s.arm].append(s)
 aggregate={a:_metrics(_components(grouped[a])) for a in ARMS}
 hit_delta=aggregate["CF2-speaker"]["carry_hit_rate"]-aggregate["CF3-wrong"]["carry_hit_rate"]
 carry_delta=aggregate["CF2-speaker"]["carry_ne_wer"]-aggregate["CF0-bare"]["carry_ne_wer"]
 wer_delta=aggregate["CF2-speaker"]["wer"]-aggregate["CF0-bare"]["wer"]
 ci_hit=_cluster_ci(scores,"CF2-speaker","CF3-wrong","carry_hit_rate");ci_carry=_cluster_ci(scores,"CF2-speaker","CF0-bare","carry_ne_wer");ci_wer=_cluster_ci(scores,"CF2-speaker","CF0-bare","wer")
 if wer_delta>0.01 or ci_wer["high"]>0.02 or aggregate["CF2-speaker"]["truncated"]>0:decision="CONFIRMATORY-HARMFUL"
 elif hit_delta>=0.05 and ci_hit["low"]>0 and carry_delta<=-0.01 and ci_carry["high"]<0 and ci_wer["high"]<=0.01:decision="SPEAKER-CONDITIONING-CONFIRMED"
 elif hit_delta>0 and carry_delta<0 and wer_delta<=0.01:decision="DIRECTIONAL-NOT-CONFIRMED"
 else:decision="SPEAKER-CONDITIONING-NOT-CONFIRMED"
 return {"schema_version":"e4-cf-verdict-v1","runtime_binding_hash":runtime.content_hash,"score_binding_hash":score.content_hash,"dialogue_clusters":len({s.uniq_id for s in scores}),"aggregate":aggregate,"contrasts":{"speaker_vs_wrong_hit_rate":{"value":hit_delta,"ci95":ci_hit},"speaker_vs_bare_carry_ne_wer":{"value":carry_delta,"ci95":ci_carry},"speaker_vs_bare_wer":{"value":wer_delta,"ci95":ci_wer}},"decision":decision}
def render_report(v:Mapping[str,object]):
 lines=[f"decision: {v['decision']}",f"dialogue_clusters: {v['dialogue_clusters']}","","arm\tWER\tcarry_NE-WER\tcarry_hit_rate\thits/total\tfalse_hint\ttruncated"]
 for a in ARMS:
  x=v["aggregate"][a];lines.append(f"{a}\t{x['wer']:.4f}\t{x['carry_ne_wer']:.4f}\t{x['carry_hit_rate']:.4f}\t{x['carry_hits']}/{x['carry_total']}\t{x['false_hint_activations']}\t{x['truncated']}")
 for name,x in v["contrasts"].items():lines.append(f"{name}: {x['value']:.4f} CI95 [{x['ci95']['low']:.4f}, {x['ci95']['high']:.4f}]")
 return "\n".join(lines)+"\n"
__all__=["CFScore","build_verdict","load_scores","render_report"]
