"""Starter commands: inspect an MPML source; no experiment execution support."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import subprocess
from argus_cli.adapters.mpml import BridgeError, preflight, spec
from argus_cli.config import ConfigError, load_sources
from argus_cli.provenance import revision

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="argus",description="Read-only local CLI research assistant")
    parser.add_argument("--config",type=Path,default=Path("sources.yaml"))
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("doctor",help="Check source configuration and print git revision")
    sub.add_parser("spec",help="Read published MPML CLI specification")
    check=sub.add_parser("preflight",help="Validate proposed MPML argv without running experiments")
    check.add_argument("--env",action="append",default=[],metavar="KEY=VALUE")
    check.add_argument("args",nargs=argparse.REMAINDER,help="Pass MPML args after --")
    args=parser.parse_args(argv)
    try:
        sources=load_sources(args.config)
        if "mpml" not in sources: raise ConfigError("Missing mpml source")
        source=sources["mpml"]
        if args.command=="doctor":
            info=revision(source.root)
            print(json.dumps({"source":"mpml","root":str(source.root),"python":str(source.python),
                "sha":info.sha,"dirty":info.dirty},indent=2))
            return 0
        if args.command=="spec":
            print(json.dumps(spec(source).document,indent=2))
            return 0
        overrides={}
        for item in args.env:
            if "=" not in item: raise ConfigError("--env requires KEY=VALUE")
            k,v=item.split("=",1)
            if not k: raise ConfigError("--env requires nonempty KEY")
            overrides[k]=v
        mpml_args=args.args[1:] if args.args and args.args[0]=="--" else args.args
        result=preflight(source,mpml_args,overrides=overrides)
        print(json.dumps(result.document,indent=2))
        return result.exit_code
    except (ConfigError,BridgeError,OSError,subprocess.CalledProcessError) as exc:
        print(f"argus: {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
