import json

from evals.intelligence_g2.contracts import PACKAGE
from evals.intelligence_g2.pr2.contracts import PR2Config
from evals.intelligence_g2.pr2.replay import run_replay as run_parent
from evals.intelligence_g2.pr3.contracts import PR3Config, data
from evals.intelligence_g2.pr3.evaluate import load_evidence_run
from evals.intelligence_g2.pr3.replay import main

from ..support import output_path
from .support import export_parent, pin
from .test_replay import args


def test_pretty_pr3_config_raw_pin_is_distinct_from_canonical_snapshot_sha(tmp_path, capsys):
    parent = export_parent(tmp_path)
    config = tmp_path / "pretty-pr3-config.json"
    config.write_text(json.dumps(data(PR3Config()), indent=2) + "\n", encoding="utf-8")
    output = output_path()
    argv = args(parent, output)
    argv[argv.index("--config") + 1] = str(config)
    argv[argv.index("--config-sha256") + 1] = pin(config)
    assert main(argv) == 0
    capsys.readouterr()
    manifest, rows = load_evidence_run(output)
    assert manifest.config_file_sha256 == pin(config)
    assert len(rows) == 2
    snapshot = next(a for a in manifest.artifacts if a.path == "config_snapshot.json")
    assert snapshot.sha256 == pin(output / "config_snapshot.json")
    assert snapshot.sha256 != manifest.config_file_sha256


def test_pretty_parent_config_remains_valid_with_its_own_raw_pin(tmp_path, capsys):
    export_parent(tmp_path)
    config = tmp_path / "pretty-pr2-config.json"
    config.write_text(json.dumps(data(PR2Config()), indent=2) + "\n", encoding="utf-8")
    raw_manifest = tmp_path / "T24-manifest.json"
    parent = output_path()
    run_parent(raw_manifest, manifest_sha256=pin(raw_manifest), timeline_id="T24", through_step="D8",
        strategy="r1", config_path=config, config_sha256=pin(config), out=parent)
    output = output_path()
    assert main(args(parent, output)) == 0
    capsys.readouterr()
    assert len(load_evidence_run(output)[1]) == 2
    assert pin(PACKAGE / "manifests/pr2_config.json") != pin(config)
