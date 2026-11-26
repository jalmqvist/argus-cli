import hashlib
import json
from unittest.mock import Mock

import pytest
from test_generation_baseline import attempt, report
from test_generation_paired import m4, saved, step

from eval.generation import baseline, datasets, paired, scoring

HISTORICAL_HASH = "3812cc04d0d738403432e5443501716edf11518cf32f054aa3b2a1835c824751"


@pytest.fixture
def fixture_dir(tmp_path, monkeypatch):
    folder = tmp_path / "fixtures"
    folder.mkdir()
    monkeypatch.setattr(datasets, "_FIXTURES", folder)
    return folder


def write_fixture(folder, dataset_id="holdout-v1", update=lambda _: None):
    baseline_data, _ = datasets.read_dataset()
    case = baseline_data["cases"][0]
    # Reuse a historical case only as unit-test input in a temporary directory.
    start = case["question"].index("MR32")
    case["constraints"] = [
        {
            "channel": "argv",
            "target": "--strategy",
            "operator": "exact",
            "values": ["MR32"],
            "span": [start, start + 4],
        }
    ]
    case["human_adjudication"] = "Test-only annotation."
    dataset = {
        "fixture_id": dataset_id,
        "version": f"test-{dataset_id}",
        "mpml_sha": baseline_data["mpml_sha"],
        "provenance": {
            "classification": "blinded_holdout"
            if dataset_id.startswith("holdout-")
            else "development",
            "author": "test-role-a",
            "reviewer": "test-role-b",
            "author_independence": "Test-only metadata.",
            "reviewer_independence": "Test-only metadata.",
            "source_bundle_sha256": "a" * 64,
            "spec_sha256": "b" * 64,
        },
        "cases": [case],
    }
    update(dataset)
    path = folder / f"{dataset_id}.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    return path


def test_default_keeps_frozen_bytes_and_historical_scoring():
    data, digest = datasets.read_dataset()
    assert len(data["cases"]) == 20
    assert digest == HISTORICAL_HASH
    selected = data["cases"][0]["id"]
    captured = report(env={"ACTIVE_PAIRS": "USDJPY"})
    legacy = saved(data, {selected: attempt(captured)}, agent=False, selected=[selected])
    legacy["manifest"]["dataset_sha256"] = digest
    assert "dataset_id" not in legacy["manifest"]
    expected = scoring.summarize(legacy, data, digest)
    assert paired.summarize(legacy, data, digest) == expected
    assert expected["outcomes"] == {"pass": 1}


@pytest.mark.parametrize(
    "bad_id",
    [
        "../baseline-v1",
        "fixtures/holdout-v1",
        "/tmp/holdout-v1.json",
        "holdout-v1.json",
        "holdout-v0",
    ],
)
def test_selection_refuses_paths_and_invalid_ids(bad_id):
    with pytest.raises(ValueError, match="Dataset must be"):
        datasets.read_dataset(bad_id)


def test_refuses_symlinked_fixtures(fixture_dir, tmp_path, monkeypatch):
    file = write_fixture(fixture_dir)
    (fixture_dir / "holdout-v2.json").symlink_to(file)
    with pytest.raises(ValueError, match="symlinks"):
        datasets.read_dataset("holdout-v2")
    alias = tmp_path / "alias"
    alias.symlink_to(fixture_dir, target_is_directory=True)
    monkeypatch.setattr(datasets, "_FIXTURES", alias)
    with pytest.raises(ValueError, match="symlinks"):
        datasets.read_dataset("holdout-v1")


@pytest.mark.parametrize(
    ("update", "message"),
    [
        (lambda data: data.update(fixture_id="holdout-v2"), "Fixture ID"),
        (lambda data: data["provenance"].update(classification="development"), "classification"),
        (lambda data: data["provenance"].update(reviewer="TEST-ROLE-A "), "separate reviewer"),
        (lambda data: data["provenance"].update(spec_sha256="bad"), "spec_sha256"),
        (lambda data: data["cases"].append(data["cases"][0]), "unique"),
        (lambda data: data["cases"][0].update(question=" "), "Invalid question"),
        (lambda data: data["cases"][0]["expected"][0].pop("env"), "argv tokens and env"),
        (
            lambda data: data["cases"][0]["expected"][0].update(verification="unknown"),
            "disposition",
        ),
        (
            lambda data: data["cases"][0]["expected"][0].update(diagnostic_codes=[42]),
            "diagnostic_codes",
        ),
        (lambda data: data["cases"][0]["constraints"][0].update(span=[0, 999]), "question span"),
        (lambda data: data["cases"][0].update(human_adjudication=[]), "human_adjudication"),
    ],
)
def test_fixture_validation(fixture_dir, update, message):
    write_fixture(fixture_dir, update=update)
    with pytest.raises(ValueError, match=message):
        datasets.read_dataset("holdout-v1")


def test_development_classification_has_its_own_identity(fixture_dir):
    path = write_fixture(fixture_dir, "development-v1")
    data, digest = datasets.read_dataset("development-v1")
    assert data["fixture_id"] == "development-v1"
    assert data["provenance"]["classification"] == "development"
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert data["cases"][0]["constraints"][0]["values"] == ["MR32"]


def report_for(dataset, digest, *, agent=False):
    case_id = dataset["cases"][0]["id"]
    captured = (
        m4(step(), env={"ACTIVE_PAIRS": "USDJPY"})
        if agent
        else report(env={"ACTIVE_PAIRS": "USDJPY"})
    )
    run = saved(dataset, {case_id: attempt(captured)}, agent=agent)
    run["manifest"].update(
        dataset_id=dataset["fixture_id"], dataset_version=dataset["version"], dataset_sha256=digest
    )
    return run


def test_score_and_compare_select_fixture_offline(fixture_dir, tmp_path, monkeypatch, capsys):
    write_fixture(fixture_dir)
    data, digest = datasets.read_dataset("holdout-v1")
    for name, agent in (("holdout-m3", False), ("holdout-m4", True)):
        (tmp_path / f"{name}.json").write_text(json.dumps(report_for(data, digest, agent=agent)))
    monkeypatch.setattr(baseline, "REPORTS", tmp_path)
    monkeypatch.setattr(baseline, "live_manifest", Mock(side_effect=AssertionError("live request")))
    assert baseline.main(["score", "holdout-m4", "--dataset", "holdout-v1"]) == 0
    assert json.loads(capsys.readouterr().out)["outcomes"] == {"pass": 1}
    assert baseline.main(["compare", "holdout-m3", "holdout-m4", "--dataset", "holdout-v1"]) == 0
    assert json.loads(capsys.readouterr().out)["dataset_id"] == "holdout-v1"
    assert baseline.main(["score", "holdout-m4"]) == 2
    assert "fixture identity" in capsys.readouterr().err


def test_compare_refuses_other_fixtures_even_with_provenance_override(fixture_dir):
    write_fixture(fixture_dir)
    data, digest = datasets.read_dataset("holdout-v1")
    first, second = report_for(data, digest), report_for(data, digest, agent=True)
    for changes, message in (
        ({"dataset_id": "holdout-v2"}, "fixture identity"),
        ({"dataset_version": "other"}, "fixture version"),
        ({"dataset_sha256": "other"}, "dataset hash"),
    ):
        other = {**second, "manifest": {**second["manifest"], **changes}}
        with pytest.raises(ValueError, match=message):
            paired.compare(first, other, data, digest, allow_provenance_mismatch=True)


def test_run_interrupt_resume_and_separate_reports(fixture_dir, tmp_path, monkeypatch, capsys):
    write_fixture(fixture_dir)
    write_fixture(fixture_dir, "holdout-v2")
    monkeypatch.setattr(baseline, "REPORTS", tmp_path)
    config, index = tmp_path / "sources.yaml", tmp_path / "index.json"
    config.write_text("fixture")
    index.write_text("fixture index")
    monkeypatch.setattr(baseline, "INDEX", index)

    def manifest(_args, data, digest, selected):
        result = report_for(data, digest)["manifest"]
        result.update(
            selected=selected,
            config=str(config),
            config_sha256=baseline.sha(config.read_bytes()),
            index_sha256=baseline.sha(index.read_bytes()),
            model=report()["model"],
            settings=report()["model"]["settings"],
        )
        return result

    monkeypatch.setattr(baseline, "live_manifest", manifest)
    fixture_attempt = attempt(report(env={"ACTIVE_PAIRS": "USDJPY"}))
    mocked = Mock(side_effect=[KeyboardInterrupt(), fixture_attempt, fixture_attempt])
    monkeypatch.setattr(baseline, "live_attempt", mocked)
    assert baseline.main(["run", "first", "--dataset", "holdout-v1", "--case", "unknown"]) == 2
    assert "Unknown case IDs" in capsys.readouterr().err
    assert baseline.main(["run", "first", "--dataset", "holdout-v1"]) == 130
    first = tmp_path / "first.json"
    assert json.loads(first.read_bytes())["summary"]["status"] == "partial"
    assert baseline.main(["run", "first", "--dataset", "holdout-v2"]) == 2
    assert "Incompatible resume" in capsys.readouterr().err
    assert baseline.main(["run", "first", "--dataset", "holdout-v1"]) == 0
    assert json.loads(first.read_bytes())["summary"]["status"] == "complete_full"
    before = first.read_bytes()
    assert baseline.main(["run", "second", "--dataset", "holdout-v2"]) == 0
    assert mocked.call_count == 3
    assert first.read_bytes() == before
    assert (
        json.loads((tmp_path / "second.json").read_bytes())["manifest"]["dataset_id"]
        == "holdout-v2"
    )
