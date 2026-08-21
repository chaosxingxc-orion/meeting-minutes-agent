"""Registered one-shot scorer for E4 speaker conditioning."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .contextasr_scoring import normalize_english
from .e4_conditioning import ARMS, E4Manifest


def _distance(left: Sequence[str], right: Sequence[str]) -> int:
    import editdistance
    return int(editdistance.eval(list(left),list(right)))


def _contains(text: str, term: str) -> bool:
    return f" {normalize_english(term)} " in f" {normalize_english(text)} "


def _entity_error(hypothesis: str, entity: str) -> int:
    target=normalize_english(entity).split(); tokens=normalize_english(hypothesis).split(); n=len(target)
    values=[]
    for start in range(len(tokens)):
        for size in range(max(1,n-1),n+2):
            if start+size<=len(tokens): values.append(_distance(target,tokens[start:start+size]))
    return min(values,default=n)


@dataclass(frozen=True)
class E4Score:
    target_id: str; uniq_id: str; arm: str; wer_errors: int; wer_tokens: int
    carry_errors: int; carry_tokens: int; carry_hits: tuple[str,...]; carry_total: int
    false_hint_activations: int; completion_tokens: int


def load_scores(manifest:E4Manifest,response_path:str|Path)->tuple[E4Score,...]:
    records={}
    for line in Path(response_path).read_text(encoding="utf-8").splitlines():
        record=json.loads(line)
        if record.get("outcome")=="ok": records[(str(record["target_id"]),str(record["arm"]))]=record
    expected={(t.target_id,a) for t in manifest.targets for a in ARMS}; missing=sorted(expected-records.keys())
    if missing: raise ValueError(f"E4 read incomplete: {len(missing)} cells missing; first={missing[:3]}")
    by_id={t.target_id:t for t in manifest.targets}; out=[]
    for target_id,arm in sorted(expected):
        target=by_id[target_id]; record=records[(target_id,arm)]; hyp=str(record["text"])
        reference=normalize_english(target.reference_text).split(); hyp_tokens=normalize_english(hyp).split()
        hits=tuple(entity for entity in target.carry_entities if _contains(hyp,entity))
        injected=tuple(str(x) for x in record.get("injected_terms",()))
        false=sum(_contains(hyp,term) and not _contains(target.reference_text,term) for term in injected)
        out.append(E4Score(target_id,target.uniq_id,arm,_distance(reference,hyp_tokens),len(reference),sum(_entity_error(hyp,e) for e in target.carry_entities),sum(len(normalize_english(e).split()) for e in target.carry_entities),hits,len(target.carry_entities),false,int(dict(record.get("usage",{})).get("completion_tokens",0))))
    return tuple(out)


def _aggregate(scores:Sequence[E4Score])->dict[str,float|int]:
    return {"wer":sum(x.wer_errors for x in scores)/sum(x.wer_tokens for x in scores),"carry_ne_wer":sum(x.carry_errors for x in scores)/sum(x.carry_tokens for x in scores),"carry_fnr":1-sum(len(x.carry_hits) for x in scores)/sum(x.carry_total for x in scores),"wer_errors":sum(x.wer_errors for x in scores),"wer_tokens":sum(x.wer_tokens for x in scores),"carry_errors":sum(x.carry_errors for x in scores),"carry_tokens":sum(x.carry_tokens for x in scores),"carry_hits":sum(len(x.carry_hits) for x in scores),"carry_total":sum(x.carry_total for x in scores),"false_hint_activations":sum(x.false_hint_activations for x in scores),"truncated":sum(x.completion_tokens>=512 for x in scores)}


def build_verdict(manifest:E4Manifest,scores:Sequence[E4Score])->dict[str,object]:
    grouped=defaultdict(list); indexed=defaultdict(dict)
    for score in scores: grouped[score.arm].append(score); indexed[score.arm][score.target_id]=score
    aggregate={arm:_aggregate(grouped[arm]) for arm in ARMS}; bare=indexed["E4-0-bare"]; speaker=indexed["E4-3-speaker"]
    corrected=broken=0
    for target in manifest.targets:
        b=set(bare[target.target_id].carry_hits); s=set(speaker[target.target_id].carry_hits)
        corrected+=len(s-b); broken+=len(b-s)
    speaker_advantage=int(aggregate["E4-3-speaker"]["carry_hits"])-int(aggregate["E4-4-wrong"]["carry_hits"])
    wer_delta=float(aggregate["E4-3-speaker"]["wer"])-float(aggregate["E4-0-bare"]["wer"])
    carry_delta=float(aggregate["E4-3-speaker"]["carry_ne_wer"])-float(aggregate["E4-0-bare"]["carry_ne_wer"])
    if wer_delta>0.01 or broken>1 or int(aggregate["E4-3-speaker"]["truncated"])>0: decision="SECOND-PASS-HARMFUL"
    elif corrected>=3 and broken<=1 and speaker_advantage>=3 and carry_delta<=0: decision="SPEAKER-CONDITIONING-REACHABLE"
    elif any(int(aggregate[a]["carry_hits"])!=int(aggregate["E4-0-bare"]["carry_hits"]) for a in ARMS[2:]): decision="CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC"
    else: decision="SPEAKER-CONDITIONING-NOT-REACHABLE"
    return {"schema_version":"e4-conditioning-verdict-v1","manifest_hash":manifest.content_hash,"aggregate":aggregate,"contrasts":{"speaker_vs_bare":{"corrected":corrected,"broken":broken,"wer_delta":wer_delta,"carry_ne_wer_delta":carry_delta},"speaker_vs_wrong":{"carry_hit_advantage":speaker_advantage}},"decision":decision,"scores":[s.__dict__ for s in scores]}


def render_report(v:Mapping[str,object])->str:
    lines=[f"decision: {v['decision']}",f"manifest_hash: {v['manifest_hash']}","","arm\tWER\tcarry_NE-WER\tcarry_FNR\thits/total\tfalse_hint\ttruncated"]
    agg=v["aggregate"]
    for arm in ARMS:
        x=agg[arm]; lines.append(f"{arm}\t{x['wer']:.4f}\t{x['carry_ne_wer']:.4f}\t{x['carry_fnr']:.4f}\t{x['carry_hits']}/{x['carry_total']}\t{x['false_hint_activations']}\t{x['truncated']}")
    c=v["contrasts"]; lines += ["",f"speaker_vs_bare corrected: {c['speaker_vs_bare']['corrected']}",f"speaker_vs_bare broken: {c['speaker_vs_bare']['broken']}",f"speaker_vs_bare WER delta: {c['speaker_vs_bare']['wer_delta']:.4f}",f"speaker_vs_bare carry_NE-WER delta: {c['speaker_vs_bare']['carry_ne_wer_delta']:.4f}",f"speaker_vs_wrong carry-hit advantage: {c['speaker_vs_wrong']['carry_hit_advantage']}"]
    return "\n".join(lines)+"\n"


__all__=["E4Score","build_verdict","load_scores","render_report"]
