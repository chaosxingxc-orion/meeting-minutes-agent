#!/usr/bin/env python3
"""Materialize leakage-separated E4 confirmatory Pass-0 manifests."""

from __future__ import annotations

import argparse, hashlib, json, sys, tarfile
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path: sys.path.insert(0, str(_SRC))
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def _tar_index(directory: Path, wanted: set[str]):
    found = {}
    for path in sorted(directory.glob("*.tar")):
        with tarfile.open(path, "r") as archive:
            for member in archive.getmembers():
                stem = Path(member.name).stem
                if member.isfile() and stem in wanted: found[stem] = (path, member.name)
        if len(found) == len(wanted): break
    return found


def _hash_members(members: dict[str, tuple[Path, str]]) -> dict[str, str]:
    grouped: dict[Path, list[tuple[str, str]]] = {}
    for uniq_id, (path, member) in members.items():
        grouped.setdefault(path, []).append((uniq_id, member))
    hashes: dict[str, str] = {}
    completed = 0
    for path, items in grouped.items():
        with tarfile.open(path, "r") as archive:
            for uniq_id, member in items:
                source = archive.extractfile(member)
                if source is None: raise ValueError(f"unreadable member: {path}/{member}")
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""): digest.update(chunk)
                hashes[uniq_id] = digest.hexdigest(); completed += 1
                if completed % 25 == 0: print(f"hashed {completed}/{len(members)}",file=sys.stderr,flush=True)
    return hashes


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--jsonl",required=True); p.add_argument("--roster",required=True); p.add_argument("--tar-dir",required=True); p.add_argument("--runtime-out",required=True); p.add_argument("--score-out",required=True); a=p.parse_args(argv)
    outputs=[Path(a.runtime_out),Path(a.score_out)]
    if any(x.exists() for x in outputs): p.error("output exists; refusing overwrite")
    roster=json.loads(Path(a.roster).read_text(encoding="utf-8")); ids=[str(x["uniq_id"]) for x in roster["entries"]]; wanted=set(ids)
    records={}
    for line in Path(a.jsonl).read_text(encoding="utf-8").splitlines():
        record=json.loads(line)
        if str(record["uniq_id"]) in wanted: records[str(record["uniq_id"])]=record
    if set(records)!=wanted: raise ValueError(f"missing JSON records: {sorted(wanted-set(records))[:5]}")
    members=_tar_index(Path(a.tar_dir),wanted)
    if set(members)!=wanted: raise ValueError(f"missing audio members: {sorted(wanted-set(members))[:5]}")
    audio_hashes=_hash_members(members)
    runtime_entries=[]; score_entries=[]
    for count,uniq_id in enumerate(ids,1):
        record=records[uniq_id]; roles={role:f"speaker_{i+1}" for i,role in enumerate(dict.fromkeys(x["role"] for x in record["dialogue"]))}
        runtime_turns=[{"index":i,"speaker_id":roles[str(t["role"])],"start":float(t["start"]),"end":float(t["end"])} for i,t in enumerate(record["dialogue"])]
        score_turns=[{"index":i,"speaker_id":roles[str(t["role"])],"reference_text":str(t["text"])} for i,t in enumerate(record["dialogue"])]
        tar_path,member=members[uniq_id]
        runtime_entries.append({"uniq_id":uniq_id,"duration":float(record["duration"]),"turns":runtime_turns,"source_tar":str(tar_path),"tar_member":member,"audio_sha256":audio_hashes[uniq_id]})
        score_entries.append({"uniq_id":uniq_id,"entity_list":[str(x) for x in record["entity_list"]],"turns":score_turns})
    common={"experiment_id":"E4-CF-287-v1","roster":str(a.roster),"roster_sha256":hashlib.sha256(Path(a.roster).read_bytes()).hexdigest()}
    runtime={"schema_version":"e4-cf-pass0-runtime-v1",**common,"entries":runtime_entries}; runtime["content_hash"]=config_hash(runtime)
    score={"schema_version":"e4-cf-pass0-score-v1",**common,"entries":score_entries}; score["content_hash"]=config_hash(score)
    outputs[0].parent.mkdir(parents=True,exist_ok=True); outputs[0].write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); outputs[1].write_text(json.dumps(score,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"runtime_hash":runtime["content_hash"],"score_hash":score["content_hash"],"dialogues":len(ids),"turns":sum(len(x["turns"]) for x in runtime_entries)})); return 0
if __name__=="__main__": raise SystemExit(main())
