from __future__ import annotations
from meeting_minutes_agent.probes.e4_confirmatory import ARMS,RuntimeBinding,RuntimeTarget,build_head_request,build_requests
def _target(uid="D1"):
 return RuntimeTarget(f"{uid}-turn002",uid,2,"speaker_1",20,30,("Global",),("Speaker",),("Wrong",),"x","y","0"*64)
def test_runtime_requests_keep_semantic_arms_equal():
 target=_target(); values=[build_head_request(target,a) for a in ARMS]
 assert values[0][0].supplied_text==()
 assert {len(terms) for _,terms in values[1:]}=={1}
 assert len({head.task_instruction for head,_ in values})==1
def test_latin_rotation_is_complete():
 requests=build_requests(RuntimeBinding({"content_hash":"x"},(_target(),_target("D2"))))
 assert [x.arm for x in requests[:4]]==list(ARMS)
 assert [x.arm for x in requests[4:8]]==list(ARMS[1:]+ARMS[:1])
