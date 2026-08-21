#!/usr/bin/env python3
"""Launch the four-arm E4 confirmatory second pass."""
from __future__ import annotations
import argparse,hashlib,json,os,sys,tarfile,tempfile
from datetime import datetime,timezone
from pathlib import Path
_SRC=Path(__file__).resolve().parent.parent/"src"
if str(_SRC) not in sys.path:sys.path.insert(0,str(_SRC))
from meeting_minutes_agent.client.budgets import BudgetLimits,CallBudget  # noqa:E402
from meeting_minutes_agent.client.receipts import FlightReceipt,ModelFileRef,ServerIdentity  # noqa:E402
from meeting_minutes_agent.client.transport import LlamaServerTransport,TransportConfig  # noqa:E402
from meeting_minutes_agent.probes.e4_confirmatory import build_requests,load_runtime_binding  # noqa:E402
def _append(h,r):h.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n");h.flush();os.fsync(h.fileno())
def _done(path):
 if not path.is_file():return set()
 return {str(r["request_id"]) for line in path.read_text(encoding="utf-8").splitlines() for r in [json.loads(line)] if r.get("outcome")=="ok"}
def _source(target,directory):
 with tarfile.open(target.source_tar,"r") as archive:
  f=archive.extractfile(target.tar_member)
  if f is None:raise RuntimeError("unreadable audio")
  data=f.read()
 if hashlib.sha256(data).hexdigest()!=target.audio_sha256:raise RuntimeError(f"audio hash mismatch {target.uniq_id}")
 p=directory/f"{target.uniq_id}.wav";p.write_bytes(data);return p
def _clip(source,target,start,end):
 import soundfile as sf
 audio,rate=sf.read(source,dtype="float32",always_2d=True);sf.write(target,audio[round(start*rate):round(end*rate)],rate,subtype="PCM_16")
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--binding",required=True);p.add_argument("--summary-only",action="store_true");p.add_argument("--base-url",default="http://127.0.0.1:8080");p.add_argument("--model-path");p.add_argument("--model-sha256");p.add_argument("--mmproj-path");p.add_argument("--mmproj-sha256");p.add_argument("--responses-out");p.add_argument("--receipt-out");p.add_argument("--resume",action="store_true");p.add_argument("--max-calls",type=int,default=3100);p.add_argument("--max-audio-seconds",type=float,default=36000);a=p.parse_args(argv)
 b=load_runtime_binding(a.binding);requests=build_requests(b);summary={"binding_hash":b.content_hash,"targets":len(b.targets),"calls":len(requests),"audio_seconds":sum(x.target.duration for x in requests)}
 if a.summary_only:print(json.dumps(summary,indent=2));return 0
 if not all((a.model_path,a.model_sha256,a.mmproj_path,a.mmproj_sha256,a.responses_out,a.receipt_out)):p.error("flight identities and outputs required")
 out=Path(a.responses_out)
 if out.exists() and not a.resume:p.error("responses exist; use --resume with new receipt")
 if Path(a.receipt_out).exists():p.error("receipt exists")
 out.parent.mkdir(parents=True,exist_ok=True);done=_done(out) if a.resume else set();remaining=[x for x in requests if x.request_id not in done];budget=CallBudget(BudgetLimits(max_calls=a.max_calls,max_audio_seconds=a.max_audio_seconds));identity=ServerIdentity(a.base_url,(ModelFileRef(a.model_path,a.model_sha256),ModelFileRef(a.mmproj_path,a.mmproj_sha256)),1);transport=LlamaServerTransport(TransportConfig(base_url=a.base_url,slots=1,max_retries=0,timeout_seconds=300),budget);receipt=FlightReceipt(identity,budget)
 with tempfile.TemporaryDirectory(prefix="e4cf-p1-") as temp,out.open("a",encoding="utf-8") as sink:
  d=Path(temp);current=None;source=None;clips={}
  for index,request in enumerate(remaining,1):
   t=request.target
   if current!=t.uniq_id:
    for path in clips.values():path.unlink(missing_ok=True)
    if source is not None:source.unlink(missing_ok=True)
    source=_source(t,d);clips={};current=t.uniq_id
   if t.target_id not in clips:clips[t.target_id]=d/f"{t.target_id}.wav";_clip(source,clips[t.target_id],t.start,t.end)
   kwargs=request.head_request.to_transport_kwargs(request_id=request.request_id,audio_path=clips[t.target_id],audio_seconds=t.duration);kwargs["decoding_params"]={"temperature":0,"seed":0,"max_tokens":512};response=transport.request(**kwargs);receipt.record(response);_append(sink,{"request_id":request.request_id,"target_id":t.target_id,"uniq_id":t.uniq_id,"turn_index":t.turn_index,"speaker_id":t.speaker_id,"arm":request.arm,"injected_terms":list(request.injected_terms),"outcome":"ok","text":response.text,"usage":dict(response.usage),"attempts":[x.as_json() for x in response.attempts],"recorded_utc":datetime.now(timezone.utc).isoformat()})
   if index%100==0:print(f"E4-CF second pass {index}/{len(remaining)}",file=sys.stderr,flush=True)
 receipt.write(a.receipt_out,repo_root=Path(__file__).resolve().parent.parent,run_id="e4-cf-287-secondpass-v1");print(json.dumps({**summary,"skipped":len(done),"flown":len(remaining)}));return 0
if __name__=="__main__":raise SystemExit(main())
