"""Correctness-first smoke suite; failures remain in raw observations."""
from pathlib import Path
import os
import platform
import statistics
import time
from .common import ForgeError, load_json, write_json
from .orchestrator import repository_root, run_all, source_commit

def benchmark(output, repetitions=3, suite="smoke"):
    if not 1 <= repetitions <= 10:
        raise ForgeError("repetitions must be between 1 and 10")
    if suite not in ("smoke", "freecad-smoke"):
        raise ForgeError("Unknown benchmark suite")
    cases = ("freecad-stepped-part",) if suite == "freecad-smoke" else ("calibration-part", "geometric-mascot")
    output=Path(output)
    if output.exists():raise ForgeError("Benchmark output already exists")
    output.mkdir(parents=True)
    rows=[]
    for case in cases:
        request=load_json(repository_root()/"examples"/case/"request.json")
        for index in range(repetitions):
            run=output/f"{case}-{index+1}"
            started=time.monotonic()
            try:
                result=run_all(request,run)
                row={"case":case,"repetition":index+1,"geometry_state":result["geometry_state"],
                     "metrics":load_json(run/"metrics.json"),"mesh_metrics":result.get("metrics",{})}
            except Exception as exc:
                row={"case":case,"repetition":index+1,"geometry_state":"blocked",
                     "failure":{"code":getattr(exc,"finding","internal_failure"),"message":str(exc)},"censored":True}
            row["wall_seconds"]=time.monotonic()-started
            rows.append(row)
            write_json(output/"raw.json",rows)
    summaries={}
    for case in cases:
        case_rows=[r for r in rows if r["case"]==case]
        values=[r["wall_seconds"] for r in case_rows]
        summaries[case]={"median_wall_seconds":statistics.median(values),"range_wall_seconds":[min(values),max(values)],
                         "passed_geometry":sum(r["geometry_state"]=="geometry_validated" for r in case_rows),"attempts":len(values),
                         "interpretation":"Includes failures/censored observations; compare only when all geometry passes."}
    report={"schema_version":"1","suite":suite,"source_commit":source_commit(),"repetitions":repetitions,
            "environment":{"system":platform.system(),"architecture":platform.machine(),"available_cores":os.cpu_count(),
                           "available_memory_bytes":None,"shared_hardware_contention":"uncontrolled"},
            "methodology":{"engine_startup":"fresh native backend processes and Blender preview process; included in stage times",
              "cold_setup_download_seconds":None,"warm_engine_execution":"not measured; no persistent engine",
              "cache":"OS filesystem caches not cleared; first repetition is not guaranteed cold",
              "peak_rss_bytes":None,"process_scope":"see each stage CPU metric; not aggregate tree memory",
              "assistant_development_seconds":None,"human_iteration_seconds":None,"model_provider_usage":None,
              "excluded_work":"Setup/download, development and human review are unavailable, not zero. No cost claim."},
            "summary":summaries,"runs":rows}
    write_json(output/"benchmark.json",report)
    return report
