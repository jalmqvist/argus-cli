import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from argus_cli.adapters.mpml import BridgeError, preflight, spec
from argus_cli.config import Source


@pytest.fixture
def source(tmp_path:Path)->Source:
    return Source("mpml",tmp_path,Path("/usr/bin/python3"),"mpml_v1","mpml.spec","mpml.preflight","main.py",())

def test_spec_only_uses_explicit_module(source:Source)->None:
    proc=subprocess.CompletedProcess([],0,json.dumps({"schema_version":1,"arguments":[]}),"")
    with patch("argus_cli.adapters.mpml.subprocess.run",return_value=proc) as run:
        result=spec(source)
    assert result.document["schema_version"]==1
    called=run.call_args.args[0]
    assert called==[str(source.python),"-m","mpml.spec"]
    assert run.call_args.kwargs["cwd"]==source.root
    assert run.call_args.kwargs.get("shell", False) is False

def test_preflight_preserves_argv_and_status(source:Source)->None:
    doc={"schema_version":1,"issues":[{"code":"TOP_N_NOT_POSITIVE","severity":"error","source":"argv","message":"invalid"}]}
    proc=subprocess.CompletedProcess([],1,json.dumps(doc),"")
    with patch("argus_cli.adapters.mpml.subprocess.run",return_value=proc) as run:
        result=preflight(source,["--recommendation-top-n","0"],overrides={"DL_SIGNALS_ENABLED":"false"})
    assert result.exit_code==1
    assert run.call_args.args[0][-2:]==["--recommendation-top-n","0"]
    assert run.call_args.kwargs["env"]["DL_SIGNALS_ENABLED"]=="false"

def test_rejects_non_json_output(source:Source)->None:
    proc=subprocess.CompletedProcess([],1,"traceback","")
    with patch("argus_cli.adapters.mpml.subprocess.run",return_value=proc), pytest.raises(
        BridgeError,match="single JSON"
    ):
        preflight(source,[])
