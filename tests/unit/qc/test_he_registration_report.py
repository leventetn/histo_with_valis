"""The H&E registration section, from a hand-made valis_pipeline run folder (REGISTER_HE).

summary.csv and placement.json follow valis_pipeline's qc.py and place.py: landmark rows per
source, tier, stage and direction, with the map checks of each stage merged in.
"""

import json

import pytest
from qc_report import build, he_registration_section, load_he_registration
from test_qc_report import minimal_metrics

HEADER = (
    "source,tier,stage,direction,n,median_um,p90_um,within_5um_percent,folded_tissue_percent,"
    "beyond_rigid_tissue_p99_um,beyond_rigid_tissue_max_um,round_trip_tissue_median_um,round_trip_tissue_p95_um"
)


def write_run(path, beyond_micro=47.2, gap=0.31, rows=True):
    """A run folder with rigid, non-rigid and micro maps; beyond_micro sets the micro map's p99."""
    (path / "qc").mkdir(parents=True)
    (path / "spatialdata").mkdir()
    lines = [HEADER]
    if rows:
        for stage, median, beyond in (
            ("rigid", 4.1, ""),
            ("nonrigid", 2.9, 31.0),
            ("micro", 2.4, beyond_micro),
        ):
            for tier in ("fine", "coarse"):
                lines.append(
                    f"auto,{tier},{stage},if_to_he,40,{median},{median * 2},90.0,0.0,{beyond},,0.3,0.8"
                )
    (path / "qc" / "summary.csv").write_text("\n".join(lines) + "\n")
    details = {"gap": gap, "angle_deg": 90, "mirrored": False} if gap is not None else {}
    (path / "placement.json").write_text(json.dumps({"method": "search", "details": details}))
    (path / "spatialdata" / "provenance.json").write_text(json.dumps({"map_stage": "micro"}))
    # A JPEG header is enough: the report only base64-inlines it.
    (path / "qc" / "overview_micro.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    return path


class TestLoad:
    def test_reads_rows_placement_and_overview(self, tmp_path):
        he = load_he_registration(write_run(tmp_path / "s1"))
        assert he["available"]
        assert len(he["rows"]) == 6
        assert he["stage"] == "micro"
        assert he["overview"].name == "overview_micro.jpg"

    def test_missing_folder_contents_is_stated(self, tmp_path):
        (tmp_path / "empty").mkdir()
        he = load_he_registration(tmp_path / "empty")
        assert not he["available"]
        assert "no qc/summary.csv" in he["reason"]

    def test_stub_output_is_not_rendered_as_data(self, tmp_path):
        he = load_he_registration(write_run(tmp_path / "s1", gap=None, rows=False))
        assert he == {"available": False, "reason": "stub run"}


class TestSection:
    def test_clean_run(self, tmp_path):
        html = he_registration_section(load_he_registration(write_run(tmp_path / "s1")))
        assert "H&amp;E registration" in html
        assert "automatic landmarks: agreement, not accuracy" in html
        for stage in ("rigid", "nonrigid", "micro"):
            assert f"<td>{stage}</td>" in html
        assert "best orientation leads the next by 0.31" in html
        assert "1% of the tissue moved more than 47 µm" in html
        assert "data:image/jpeg;base64," in html
        assert "preprocessing/he_registration/s1/qc/" in html
        assert "&#10007;" not in html  # no failed check

    def test_beyond_rigid_above_100_um_is_flagged(self, tmp_path):
        html = he_registration_section(load_he_registration(write_run(tmp_path / "s1", beyond_micro=442.0)))
        assert "1% of the tissue moved more than 442 µm" in html
        assert "&#10007;" in html

    def test_ambiguous_placement_is_flagged(self, tmp_path):
        html = he_registration_section(load_he_registration(write_run(tmp_path / "s1", gap=0.04)))
        assert "best orientation leads the next by 0.04 (ambiguous below 0.1)" in html
        assert "&#10007;" in html

    def test_absence_is_stated_not_hidden(self):
        html = he_registration_section({"available": False, "reason": "stub run"})
        assert "Not computed: stub run." in html

    def test_none_renders_nothing(self):
        assert he_registration_section(None) == ""


@pytest.mark.parametrize("with_he", [False, True])
def test_whole_page_still_renders(tmp_path, with_he):
    he = load_he_registration(write_run(tmp_path / "s1")) if with_he else None
    page = build(minimal_metrics(), he_registration=he)
    assert page.rstrip().endswith("</html>")
    assert ("H&amp;E registration" in page) is with_he
