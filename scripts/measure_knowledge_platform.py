"""Small, declared local concurrency observation; not an SLA/load acceptance campaign."""
import argparse
import ctypes
import json
import threading
import time
from datetime import UTC,datetime
from uuid import uuid4

from knowledge_platform import STATE,retain
from verify_knowledge_platform import login,require,API,wait_state
from campus247.domain.shared.values import generate_uuid7
from campus247_worker.knowledge import available_memory


def memory(pid):
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("faults",wintypes.DWORD)]+[(key,ctypes.c_size_t) for key in
            ("peak_ws","ws","peak_paged","paged","peak_nonpaged","nonpaged","pagefile","peak_pagefile")]
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1010,False,pid)
    if not handle:
        return None
    try:
        counters=Counters(); counters.cb=ctypes.sizeof(counters)
        api=ctypes.WinDLL("psapi",use_last_error=True).GetProcessMemoryInfo
        api.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if not api(handle,ctypes.byref(counters),counters.cb):
            return None
        return {"working_set":counters.ws,"lifetime_peak_working_set":counters.peak_ws}
    finally:
        kernel.CloseHandle(handle)


def descendants(roots):
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[("size",wintypes.DWORD),("usage",wintypes.DWORD),("pid",wintypes.DWORD),("heap",ctypes.c_size_t),
            ("module",wintypes.DWORD),("threads",wintypes.DWORD),("parent",wintypes.DWORD),("priority",wintypes.LONG),
            ("flags",wintypes.DWORD),("name",wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:
        return {label:{pid} for label,pid in roots.items()}
    parents={}
    try:
        entry=Entry(); entry.size=ctypes.sizeof(entry)
        found=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while found:
            parents[entry.pid]=entry.parent
            found=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    result={}
    for label,root in roots.items():
        selected={root}
        while True:
            new={pid for pid,parent in parents.items() if parent in selected}
            if new <= selected:
                break
            selected |= new
        result[label]=selected
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--process",action="append",default=[],help="Known task-owned label=PID, verified before this command")
    args=parser.parse_args()
    owned={label:int(pid) for label,pid in (item.split("=",1) for item in args.process)}
    if any(pid<=0 for pid in owned.values()):
        raise ValueError("Exact positive task-owned PIDs required")
    stamp=datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    report={"at":stamp,"window":"idle + two chat turns while one TXT ingestion runs",
        "scope":"synthetic text, one worker, small observation; no production/load guarantee",
        "working_set_sum_is_unique_physical_RAM":False,"processes":owned,"samples":[]}
    stop=threading.Event()
    def sample():
        while not stop.is_set():
            trees=descendants(owned)
            measurements={}
            for label,pids in trees.items():
                values=[value for pid in pids if (value:=memory(pid)) is not None]
                measurements[label]={"working_set":sum(v["working_set"] for v in values),"sampled_process_count":len(values)} if values else None
            report["samples"].append({"elapsed_seconds":time.monotonic()-started,"available_bytes":available_memory(),"processes":measurements})
            stop.wait(.2)
    started=time.monotonic()
    sampler=threading.Thread(target=sample,daemon=True)
    sampler.start()
    author,student=login("KA01"),login("SV01")
    try:
        time.sleep(2)
        content=("Nội dung kiểm thử tài nguyên local; không phải quy định của trường. "*45).encode()
        key=str(uuid4())
        metadata={"title":"Kiểm chứng tài nguyên local", "owner_unit":"Local test", "canonical_uri":"urn:resource-test:"+key,
            "programs":["PUBLIC"],"audiences":["STUDENT","KNOWLEDGE_ADMIN"],"effective_from":None}
        accepted=require(author.post(API+"/uploads",data={"metadata":json.dumps(metadata)},
            files={"file":("resource-test.txt",content,"text/plain")},headers={"Idempotency-Key":key}),202)
        report["job_id"]=accepted["job_id"]
        conversation=require(student.post("/v1/conversations",json={"mode":"temporary"}),201)
        identifier=conversation.get("conversation_id",conversation.get("id"))
        latencies,outcomes=[],[]
        for question in ("Phòng thí nghiệm Sao Mai mở cửa từ mấy giờ đến mấy giờ?",
                         "Phòng thí nghiệm Sao Mai có quy định mức học phí năm 2099 là bao nhiêu?"):
            turn_started=time.monotonic()
            response=student.post(f"/v1/conversations/{identifier}/messages:stream",json={"content":question,"client_id":generate_uuid7()})
            latencies.append(round((time.monotonic()-turn_started)*1000,2))
            final=None
            for block in response.text.split("\n\n"):
                if "event: message.completed\n" in block:
                    final=json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: ")))
            outcomes.append({"http_status":response.status_code,"status":final.get("status") if final else None,
                             "response_class":final.get("response_class") if final else None})
        state=wait_state(author,lambda s:any(j["id"]==accepted["job_id"] and j["state"] in {"SUCCEEDED","FAILED"} for j in s["jobs"]),seconds=120)
        job=next(j for j in state["jobs"] if j["id"]==accepted["job_id"])
        report.update(chat_count=2,chat_end_to_end_ms=latencies,chat_outcomes=outcomes,job=job,
            passed=job["state"]=="SUCCEEDED" and outcomes[0]["status"]=="answered" and outcomes[1]["status"]=="abstained")
    finally:
        author.close(); student.close(); stop.set(); sampler.join(timeout=2)
        report["duration_seconds"]=round(time.monotonic()-started,2)
        report["minimum_available_bytes"]=min((s["available_bytes"] for s in report["samples"] if s["available_bytes"] is not None),default=None)
        report["sampled_peak_working_set"]={label:max((s["processes"][label]["working_set"] for s in report["samples"] if s["processes"][label]),default=None) for label in owned}
        target=STATE / ("resource-observation-"+stamp+".json")
        retain(target,report)
        print(json.dumps({k:report[k] for k in ("passed","duration_seconds","minimum_available_bytes","sampled_peak_working_set","chat_end_to_end_ms","chat_outcomes") if k in report} | {"report":str(target)}),flush=True)


if __name__=="__main__":
    main()
