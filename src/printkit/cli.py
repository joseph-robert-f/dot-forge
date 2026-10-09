"""Stable JSON stdout; diagnostics on stderr. See docs/quickstart.md."""
import argparse
import json
from pathlib import Path
import sys
from .common import ForgeError, load_json
from .contracts import check_request

def parser():
    root=argparse.ArgumentParser(prog="printkit",description="Bounded reviewed 3D model generation with independent evidence")
    commands=root.add_subparsers(dest="command",required=True)
    cmd=commands.add_parser("doctor");cmd.add_argument("--json",action="store_true");smokes=cmd.add_mutually_exclusive_group();smokes.add_argument("--smoke",metavar="NEW_RUN");smokes.add_argument("--all-smoke",metavar="NEW_DIR");cmd.add_argument("--backend",choices=["blender","freecad"],default="blender")
    cmd=commands.add_parser("check-request");cmd.add_argument("request")
    cmd=commands.add_parser("check-intent",help="v2: validate an intent spec");cmd.add_argument("intent")
    cmd=commands.add_parser("check-plan",help="v2: validate a build plan");cmd.add_argument("plan");cmd.add_argument("--intent")
    cmd=commands.add_parser("build",help="v2: build a plan in FreeCAD and check it against its intent");cmd.add_argument("--intent",required=True);cmd.add_argument("--plan",required=True);cmd.add_argument("--output",required=True)
    cmd=commands.add_parser("printability",help="any STL: will it print and survive? never judges likeness");cmd.add_argument("stl");cmd.add_argument("--bed",type=float,nargs=3,metavar=("X","Y","Z"));cmd.add_argument("--min-wall",type=float,default=0.8);cmd.add_argument("--overhang-deg",type=float,default=45.0);cmd.add_argument("--samples",type=int,default=600)
    cmd=commands.add_parser("conform",help="v2: recheck a measurement against an intent");cmd.add_argument("--intent",required=True);cmd.add_argument("--measurement",required=True)
    for name in ("run","generate"):
        cmd=commands.add_parser(name);cmd.add_argument("--request",required=True);cmd.add_argument("--output",required=True)
    for name in ("validate","render","inspect","resume","bundle"):
        cmd=commands.add_parser(name);cmd.add_argument("--run",required=True)
        if name=="validate":cmd.add_argument("--profile",default="solid-single-part",choices=["solid-single-part"])
        if name=="bundle":cmd.add_argument("--output")
    cmd=commands.add_parser("verify-bundle");cmd.add_argument("bundle")
    cmd=commands.add_parser("benchmark");cmd.add_argument("--suite",default="smoke",choices=["smoke","freecad-smoke"]);cmd.add_argument("--output",required=True);cmd.add_argument("--repetitions",type=int,default=3)
    return root

def report_exit(report):
    if report.get("geometry_state")=="blocked":return 4
    if report.get("print_assessment",{}).get("state")=="blocked":return 4
    if report.get("overall_state")=="blocked":return 4
    if report.get("overall_state")=="needs_review":return 5
    return 0

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        from . import orchestrator as workflow
        code=0
        if args.command=="doctor":
            from .doctor import doctor
            result=doctor(args.smoke,args.backend,args.all_smoke)
            if result[args.backend]["status"] in ("unavailable","incompatible"):code=3
            if args.smoke and result.get("smoke_geometry_state")!="geometry_validated":code=4
            if args.all_smoke and result["default_profile"]["smoke_status"]!="pass":code=4
        elif args.command=="check-request":
            check_request(load_json(args.request));result={"schema_version":"1","status":"pass"}
        elif args.command=="check-intent":
            from .intent import check_intent,summarize
            result=summarize(check_intent(load_json(args.intent)))
        elif args.command=="check-plan":
            from .intent import check_intent
            from .plan import check_plan
            result=check_plan(load_json(args.plan),check_intent(load_json(args.intent)) if args.intent else None)
        elif args.command=="build":
            from .forge import build
            result=build(load_json(args.intent),load_json(args.plan),Path(args.output));code=report_exit(result)
        elif args.command=="printability":
            from .printability import assess
            if not (0<args.min_wall<=50 and 0<args.overhang_deg<90 and 1<=args.samples<=20000) or (args.bed and not all(0<b<=10000 for b in args.bed)):
                raise ForgeError("--min-wall, --overhang-deg, --samples or --bed is out of range")
            result=assess(args.stl,bed_mm=args.bed,min_wall_mm=args.min_wall,overhang_deg=args.overhang_deg,samples=args.samples)
            code=4 if result["state"]=="blocked" else 5
        elif args.command=="conform":
            from .intent import check_intent
            from .conformance import conform
            result=conform(check_intent(load_json(args.intent)),load_json(args.measurement))
            code=4 if result["intent_state"]=="blocked" else 0
        elif args.command in ("run","generate"):
            request=check_request(load_json(args.request))
            result=(workflow.run_all if args.command=="run" else workflow.generate)(request,Path(args.output))
            code=report_exit(result)
        elif args.command in ("validate","render","resume"):
            if (Path(args.run)/"COMPLETE").exists() and args.command in ("validate","render"):
                raise ForgeError("Completed attempts are immutable; use a fresh attempt for changed stages",4,"immutable_attempt")
            result=getattr(workflow,args.command)(Path(args.run));code=report_exit(result.get("validation",result))
        elif args.command=="inspect":
            from .bundle import verify_run
            manifest=verify_run(args.run)
            result={"schema_version":"1","integrity":"pass","manifest":manifest,"validation":load_json(Path(args.run)/"validation.json")}
            code=report_exit(result["validation"])
        elif args.command=="bundle":
            from .bundle import create_bundle
            result=create_bundle(args.run,args.output)
        elif args.command=="verify-bundle":
            from .bundle import verify_bundle
            result=verify_bundle(args.bundle)
        elif args.command=="benchmark":
            from .benchmark import benchmark
            result=benchmark(args.output,args.repetitions,args.suite)
            if any(r["geometry_state"]!="geometry_validated" for r in result["runs"]):code=4
        print(json.dumps(result,sort_keys=True,allow_nan=False))
        return code
    except ForgeError as exc:
        print(str(exc),file=sys.stderr)
        print(json.dumps({"schema_version":"1","status":"error","code":exc.finding,"message":str(exc)}))
        return exc.code
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f"Internal failure: {exc}",file=sys.stderr)
        print(json.dumps({"schema_version":"1","status":"error","code":"internal_failure","message":str(exc)}))
        return 7

if __name__=="__main__":raise SystemExit(main())
