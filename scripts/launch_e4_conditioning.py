#!/usr/bin/env python3
"""Launch the registered E4 six-arm fixed second-pass smoke."""

from __future__ import annotations

import argparse, hashlib, json, os, sys, tarfile, tempfile
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path: sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.probes.e4_conditioning import build_requests, load_manifest  # noqa: E402


def _append(handle, record):
    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"); handle.flush(); os.fsync(handle.fileno())


def _extract(target, directory: Path) -> Path:
    with tarfile.open(target.source_tar, "r") as archive:
        source = archive.extractfile(target.tar_member)
        if source is None: raise RuntimeError(f"unreadable tar member: {target.tar_member}")
        data = source.read()
    if hashlib.sha256(data).hexdigest() != target.audio_sha256: raise RuntimeError(f"audio hash mismatch: {target.uniq_id}")
    path = directory / f"{target.uniq_id}.wav"; path.write_bytes(data); return path


def _slice(source: Path, target: Path, start: float, end: float) -> None:
    import soundfile as sf
    audio, rate = sf.read(source, dtype="float32", always_2d=True)
    sf.write(target, audio[round(start * rate):round(end * rate)], rate, subtype="PCM_16")


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--manifest",required=True); p.add_argument("--summary-only",action="store_true")
    p.add_argument("--base-url",default="http://127.0.0.1:8080"); p.add_argument("--model-path"); p.add_argument("--model-sha256")
    p.add_argument("--mmproj-path"); p.add_argument("--mmproj-sha256"); p.add_argument("--responses-out"); p.add_argument("--receipt-out")
    p.add_argument("--max-calls",type=int,default=216); p.add_argument("--max-audio-seconds",type=float,default=2500.0); args=p.parse_args(argv)
    manifest=load_manifest(args.manifest); requests=build_requests(manifest)
    summary={"manifest_hash":manifest.content_hash,"targets":len(manifest.targets),"calls":len(requests),"audio_seconds":sum(r.target.duration for r in requests)}
    if args.summary_only: print(json.dumps(summary,indent=2)); return 0
    if not all((args.model_path,args.model_sha256,args.mmproj_path,args.mmproj_sha256,args.responses_out,args.receipt_out)): p.error("flight mode requires model/mmproj identities and outputs")
    response_path=Path(args.responses_out)
    if response_path.exists(): p.error(f"responses file exists; refusing overwrite: {response_path}")
    response_path.parent.mkdir(parents=True,exist_ok=True)
    budget=CallBudget(BudgetLimits(max_calls=args.max_calls,max_audio_seconds=args.max_audio_seconds))
    identity=ServerIdentity(args.base_url,(ModelFileRef(args.model_path,args.model_sha256),ModelFileRef(args.mmproj_path,args.mmproj_sha256)),1)
    transport=LlamaServerTransport(TransportConfig(base_url=args.base_url,slots=1,max_retries=0,timeout_seconds=300),budget); receipt=FlightReceipt(identity,budget)
    with tempfile.TemporaryDirectory(prefix="e4-") as temp, response_path.open("a",encoding="utf-8") as sink:
        directory=Path(temp); sources={}; clips={}
        for index,request in enumerate(requests,1):
            target=request.target
            if target.uniq_id not in sources: sources[target.uniq_id]=_extract(target,directory)
            if target.target_id not in clips:
                clips[target.target_id]=directory/f"{target.target_id}.wav"; _slice(sources[target.uniq_id],clips[target.target_id],target.start,target.end)
            kwargs=request.head_request.to_transport_kwargs(request_id=request.request_id,audio_path=clips[target.target_id],audio_seconds=target.duration)
            kwargs["decoding_params"]={"temperature":0,"seed":0,"max_tokens":512}; response=transport.request(**kwargs); receipt.record(response)
            _append(sink,{"request_id":request.request_id,"target_id":target.target_id,"uniq_id":target.uniq_id,"turn_index":target.turn_index,"speaker_id":target.speaker_id,"arm":request.arm,"injected_terms":list(request.injected_terms),"outcome":"ok","text":response.text,"usage":dict(response.usage),"attempts":[x.as_json() for x in response.attempts],"recorded_utc":datetime.now(timezone.utc).isoformat()})
            if index%12==0: print(f"E4 {index}/{len(requests)}",file=sys.stderr,flush=True)
    receipt.write(args.receipt_out,repo_root=Path(__file__).resolve().parent.parent,run_id="e4-conditioning-36-v1")
    print(json.dumps(summary)); return 0


if __name__=="__main__": raise SystemExit(main())
