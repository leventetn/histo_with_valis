"""Tests for bin/he_registration_config.py: the valis_pipeline config REGISTER_HE writes."""

import json
from pathlib import Path

import pytest
from he_registration_config import VALIS, build_config


def config(**over):
    args = dict(
        name="s1",
        ifimage="if/s1.ome.tif",
        channel_index=0,
        heimage="he/s1.svs",
        placement="search",
        placement_check="stop",
        micro_um="native",
    )
    return build_config(**(args | over))


def test_fixed_settings():
    c = config()
    assert c["valis"] == VALIS == {"processed_px": 1000, "non_rigid_px": 4000, "non_rigid": "deepflow"}
    assert c["same_section"] is True
    assert c["inverse"] == "invert"
    assert c["spatialdata_mode"] == "none"
    assert c["outdir"] == "."


def test_names_give_he_on_if():
    c = config()
    assert (c["reference"]["name"], c["moving"]["name"]) == ("if", "he")
    assert c["name"] == "s1"


def test_paths_are_absolute_and_channel_is_by_index():
    c = config(channel_index="2")
    assert Path(c["reference"]["path"]).is_absolute()
    assert Path(c["moving"]["path"]).is_absolute()
    assert c["reference"]["channel_index"] == 2
    assert "channel" not in c["reference"]


def test_micro_um():
    assert config(micro_um="native")["micro_um"] == "native"
    assert config(micro_um="0.5")["micro_um"] == 0.5
    with pytest.raises(ValueError, match="greater than 0"):
        config(micro_um="0")


def test_cli_prints_json(tmp_path, monkeypatch, capsys):
    from he_registration_config import main

    monkeypatch.chdir(tmp_path)
    argv = ["he_registration_config.py", "--name", "s1", "--if-image", "a.ome.tif", "--channel-index", "1"]
    monkeypatch.setattr("sys.argv", [*argv, "--he-image", "b.svs", "--placement-check", "skip"])
    assert main() == 0
    c = json.loads(capsys.readouterr().out)
    assert c["placement_check"] == "skip"
    assert c["reference"]["path"] == str(Path.cwd() / "a.ome.tif")
