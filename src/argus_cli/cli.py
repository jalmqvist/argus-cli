"""Starter commands: inspect an MPML source; no experiment execution support."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from argus_cli.adapters.mpml import BridgeError, preflight, spec
from argus_cli.config import ConfigError, load_sources
from argus_cli.mpml_help import describe
from argus_cli.provenance import revision


class _CommandParser(argparse.ArgumentParser):
    accepts_flag_query = False

    def parse_known_args(self, args=None, namespace=None):
        # Only normalize lookup arguments after argparse has selected the subcommand.
        if (
            self.accepts_flag_query
            and args is not None
            and len(args) == 1
            and args[0].startswith("-")
            and args[0] not in {"-", "--", "-h", "--help"}
        ):
            args = ["--", args[0]]
        return super().parse_known_args(args, namespace)


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="argus",description="Read-only local CLI research assistant")
    parser.add_argument("--config",type=Path,default=Path("sources.yaml"))
    sub=parser.add_subparsers(dest="command",required=True,parser_class=_CommandParser)
    sub.add_parser("doctor",help="Check source configuration and print git revision")
    sub.add_parser("spec",help="Read published MPML CLI specification")
    check=sub.add_parser("preflight",help="Validate proposed MPML argv without running experiments")
    check.add_argument("--env",action="append",default=[],metavar="KEY=VALUE")
    check.add_argument("args",nargs=argparse.REMAINDER,help="Pass MPML args after --")
    inspect = sub.add_parser("inspect", help="Look up an exact MPML flag or environment variable")
    inspect.accepts_flag_query = True
    inspect.add_argument("query", metavar="flag-or-env")
    explain = sub.add_parser("explain", help="Explain an MPML spec topic")
    explain.accepts_flag_query = True
    explain.add_argument(
        "query",
        metavar="topic",
        help="precedence, warnings, strategies, behavioral-surfaces, source-edit-only, "
        "a precedence setting, an issue code, or a flag or environment variable",
    )
    recipe = sub.add_parser("recipe", help="Preflight a supported MPML launch pattern")
    recipe.add_argument("query", metavar="pattern", choices=["defaults"], help="defaults")
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
        if args.command in {"inspect", "explain", "recipe"}:
            report, exit_code = describe(source, args.command, args.query)
            print(json.dumps(report, indent=2))
            return exit_code
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
    except (ConfigError,BridgeError,OSError,subprocess.SubprocessError) as exc:
        print(f"argus: {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
