#!/usr/bin/env python3
"""Launch E4 confirmatory Pass 0 from the runtime-only manifest."""
from __future__ import annotations
import argparse,hashlib,json,os,sys,tarfile,tempfile
from datetime import datetime,timezone
from pathlib import Path
_SRC=Path(__file__).resolve().parent.parent/"src"
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from meeting_minutes_agent.client.budgets import BudgetLimits,CallBudget  # noqa:E402
from meeting_minutes_agent.client.receipts import FlightReceipt,ModelFileRef,ServerIdentity  # noqa:E402
from meeting_minutes_agent.client.transport import LlamaServerTransport,TransportConfig  # noqa:E402
from meeting_minutes_agent.heads.request import HeadRequest  # noqa:E402
from meeting_minutes_agent.probes.contextasr import SYSTEM_INSTRUCTION,TEMPLATE_ID,TEMPLATE_SHA256  # noqa:E402
from meeting_minutes_agent.probes.e4_confirmatory import load_pass0_runtime  # noqa:E402
def _append(h,r): h.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n");h.flush();os.fsync(h.fileno())
def _done(path):
 if not path.is_file(): return set()
 return {(str(r["uniq_id"]),int(r["turn_index"])) for line in path.read_text(encoding="utf-8").splitlines() for r in [json.loads(line)] if r.get("outcome")=="ok"}
def _clips(entry,directory):
 import soundfile as sf
 with tarfile.open(entry.source_tar,"r") as archive:
  source=archive.extractfile(entry.tar_member)
  if source is None: raise RuntimeError(f"unreadable {entry.tar_member}")
  data=source.read()
 if hashlib.sha256(data).hexdigest()!=entry.audio_sha256: raise RuntimeError(f"audio hash mismatch: {entry.uniq_id}")
 whole=directory/f"{entry.uniq_id}.wav";whole.write_bytes(data);audio,rate=sf.read(whole,dtype="float32",always_2d=True);out={}
 for turn in entry.turns:
  path=directory/f"{entry.uniq_id}-turn{turn.index:03d}.wav";sf.write(path,audio[round(turn.start*rate):round(turn.end*rate)],rate,subtype="PCM_16");out[turn.index]=path
 whole.unlink();return out
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--manifest",required=True);p.add_argument("--summary-only",action="store_true");p.add_argument("--base-url",default="http://127.0.0.1:8080");p.add_argument("--model-path");p.add_argument("--model-sha256");p.add_argument("--mmproj-path");p.add_argument("--mmproj-sha256");p.add_argument("--responses-out");p.add_argument("--receipt-out");p.add_argument("--resume",action="store_true");p.add_argument("--max-calls",type=int,default=3822);p.add_argument("--max-audio-seconds",type=float,default=44000);a=p.parse_args(argv)
 m=load_pass0_runtime(a.manifest);all_turns=[(e,t) for e in m.entries for t in e.turns];summary={"manifest_hash":m.content_hash,"dialogues":len(m.entries),"calls":len(all_turns),"audio_seconds":sum(t.duration for _,t in all_turns)}
 if a.summary_only: print(json.dumps(summary,indent=2));return 0
 if not all((a.model_path,a.model_sha256,a.mmproj_path,a.mmproj_sha256,a.responses_out,a.receipt_out)):p.error("flight identities and outputs required")
 out=Path(a.responses_out)
 if out.exists() and not a.resume:p.error("responses exist; use --resume with a new receipt path")
 if Path(a.receipt_out).exists():p.error("receipt output exists")
 out.parent.mkdir(parents=True,exist_ok=True);done=_done(out) if a.resume else set();remaining=[x for x in all_turns if (x[0].uniq_id,x[1].index) not in done]
 budget=CallBudget(BudgetLimits(max_calls=a.max_calls,max_audio_seconds=a.max_audio_seconds));identity=ServerIdentity(a.base_url,(ModelFileRef(a.model_path,a.model_sha256),ModelFileRef(a.mmproj_path,a.mmproj_sha256)),1);transport=LlamaServerTransport(TransportConfig(base_url=a.base_url,slots=1,max_retries=0,timeout_seconds=300),budget);receipt=FlightReceipt(identity,budget);head=HeadRequest(SYSTEM_INSTRUCTION,(),{},TEMPLATE_ID,TEMPLATE_SHA256)
 with tempfile.TemporaryDirectory(prefix="e4cf-p0-") as temp,out.open("a",encoding="utf-8") as sink:
  directory=Path(temp);current_id=None;clips={}
  for index,(entry,turn) in enumerate(remaining,1):
   if current_id!=entry.uniq_id:
    for path in clips.values():path.unlink(missing_ok=True)
    clips=_clips(entry,directory);current_id=entry.uniq_id
   request_id=f"e4cf-p0-{entry.uniq_id}-turn{turn.index:03d}";kwargs=head.to_transport_kwargs(request_id=request_id,audio_path=clips[turn.index],audio_seconds=turn.duration);kwargs["decoding_params"]={"temperature":0,"seed":0,"max_tokens":512};response=transport.request(**kwargs);receipt.record(response);_append(sink,{"request_id":request_id,"uniq_id":entry.uniq_id,"turn_index":turn.index,"speaker_id":turn.speaker_id,"outcome":"ok","text":response.text,"usage":dict(response.usage),"attempts":[x.as_json() for x in response.attempts],"recorded_utc":datetime.now(timezone.utc).isoformat()})
   if index%100==0:print(f"E4-CF Pass0 {index}/{len(remaining)}",file=sys.stderr,flush=True)
 receipt.write(a.receipt_out,repo_root=Path(__file__).resolve().parent.parent,run_id="e4-cf-287-pass0-v1");print(json.dumps({**summary,"skipped":len(done),"flown":len(remaining)}));return 0
if __name__=="__main__":raise SystemExit(main())
