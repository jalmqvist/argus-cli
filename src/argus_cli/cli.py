"""Read-only commands for inspecting and preflighting MPML launches."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from argus_cli.adapters.mpml import BridgeError, preflight, spec
from argus_cli.config import ConfigError, load_sources
from argus_cli.mpml_help import describe
from argus_cli.ollama import EmbeddingError
from argus_cli.provenance import revision
from argus_cli.retrieval import MODES, RetrievalError, build, retrieve


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
    index = sub.add_parser("index", help="Build the local MPML knowledge index")
    index.add_argument("--embed", metavar="MODEL", help="Store embeddings from local Ollama")
    search = sub.add_parser("retrieve", help="Find cited MPML evidence in the local index")
    search.add_argument("query")
    search.add_argument("--mode", choices=MODES, default="lexical")
    search.add_argument("--limit", type=int, default=5)
    answer = sub.add_parser("ask", help="Generate and preflight a cited MPML recipe")
    answer.add_argument("question")
    answer.add_argument("--agent", action="store_true", help="Use bounded LangGraph orchestration")
    answer.add_argument("--model", default="qwen2.5-coder:7b")
    answer.add_argument(
        "--retrieval-mode", choices=("lexical", "embedding", "hybrid"), default="hybrid"
    )
    answer.add_argument("--temperature", type=float, default=0.0)
    answer.add_argument("--seed", type=int, default=42)
    answer.add_argument("--timeout", type=float, default=180.0, metavar="SECONDS")
    args=parser.parse_args(argv)
    if args.command == "ask" and not (
        args.question.strip()
        and len(args.question) <= 4000
        and 0 <= args.temperature <= 2
        and 0 < args.timeout <= 600
        and args.seed >= 0
        and args.model.strip()
    ):
        answer.error(
            "requires a question (up to 4000 characters), a model, temperature 0–2, "
            "a nonnegative seed, and timeout in (0, 600] seconds"
        )
    if args.command == "retrieve" and (args.limit < 1 or not args.query.strip()):
        search.error("retrieve requires a nonblank query and a positive --limit")
    try:
        sources=load_sources(args.config)
        if "mpml" not in sources: raise ConfigError("Missing mpml source")
        source=sources["mpml"]
        if args.command == "ask":
            try:
                from argus_cli.ask import ask
                from argus_cli.generation import GenerationSettings
            except ModuleNotFoundError as exc:
                extra = "llm,agent" if args.agent else "llm"
                raise ConfigError(
                    f"argus ask requires the optional dependencies: pip install 'argus-cli[{extra}]'"
                ) from exc
            workflow = ask
            if args.agent:
                from argus_cli.live_agent import ask_agent

                workflow = ask_agent
            report = workflow(
                source,
                args.question,
                model=args.model,
                retrieval_mode=args.retrieval_mode,
                settings=GenerationSettings(
                    temperature=args.temperature,
                    seed=args.seed,
                    timeout_seconds=args.timeout,
                ),
            )
            print(json.dumps(report, indent=2))
            return 0 if report["command"] is not None else 1
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
        if args.command in {"index", "retrieve"}:
            if args.command == "index":
                report = build(source, args.embed)
            else:
                report = retrieve(source, args.query, args.mode, args.limit)
            print(json.dumps(report, indent=2))
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
    except (
        ConfigError, BridgeError, EmbeddingError, RetrievalError, OSError, UnicodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"argus: {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
