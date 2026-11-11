"""Tests for bin/add_registered_image.py: the registered H&E written into a real SpatialData store
built in tmp_path, from a run folder laid out as valis_pipeline writes it."""

import json

import numpy as np
import pytest
from add_registered_image import ATTR, add_registered_image

SUMMARY = """source,tier,stage,direction,n,median_um,p90_um,within_5um_percent,folded_tissue_percent,beyond_rigid_tissue_p99_um
auto,fine,rigid,if_to_he,40,3.1,6.0,80.0,,
auto,fine,micro,if_to_he,40,2.4,4.1,95.0,0.0,47.2
"""


@pytest.fixture
def store(tmp_path):
    """A 2-channel 64x64 IF store with a 2-level pyramid, as TO_SPATIALDATA writes it."""
    import spatialdata as sd
    from spatialdata.models import Image2DModel

    data = np.random.default_rng(0).integers(0, 1000, size=(2, 64, 64), dtype=np.uint16)
    image = Image2DModel.parse(
        data, dims=("c", "y", "x"), c_coords=["DNA_1", "CD45"], scale_factors=[2], chunks=(1, 32, 32)
    )
    path = tmp_path / "sample.zarr"
    sdata = sd.SpatialData(images={"sample": image})
    sdata.attrs["cell_segmentation_image"] = "sample"
    sdata.write(path)
    return path


def he_tif(path, height=64, width=64):
    """An RGB pyramid OME-TIFF as valis_pipeline's write_pyramid makes it (axes YXS)."""
    import tifffile

    rgb = np.random.default_rng(1).integers(0, 255, size=(height, width, 3), dtype=np.uint8)
    with tifffile.TiffWriter(path, bigtiff=True, ome=True) as tif:
        tif.write(rgb, subifds=1, photometric="rgb", tile=(16, 16), metadata={"axes": "YXS"})
        tif.write(rgb[::2, ::2], subfiletype=1, photometric="rgb", tile=(16, 16))
    return path, rgb


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / "sample"
    for sub in ("inputs", "qc", "spatialdata"):
        (run / sub).mkdir(parents=True)
    (run / "registration.json").write_text(
        json.dumps({"state": "complete", "code_version": "v1.0.0", "versions": {"valis-wsi": "1.2.0"}})
    )
    (run / "placement.json").write_text(
        json.dumps({"method": "search", "ambiguous": False, "details": {"gap": 0.31}})
    )
    (run / "spatialdata" / "provenance.json").write_text(
        json.dumps(
            {"state": "complete", "map_stage": "micro", "mode": "none", "moving_covers_fraction": 0.98}
        )
    )
    (run / "inputs" / "if.json").write_text(json.dumps({"um_per_px": 0.65}))
    (run / "inputs" / "he.json").write_text(json.dumps({"um_per_px": 0.26}))
    (run / "qc" / "summary.csv").write_text(SUMMARY)
    return run


def test_adds_the_element_on_the_store_grid(store, run_dir, tmp_path):
    import spatialdata as sd
    from spatialdata.transformations import Identity, get_transformation

    tif, rgb = he_tif(tmp_path / "he.ome.tif")
    add_registered_image(store, tif, run_dir, "sample_he", "preprocessing/he_registration/sample")

    s = sd.read_zarr(store)
    assert sorted(s.images) == ["sample", "sample_he"]
    level0 = next(iter(s["sample_he"]["scale0"].values()))
    assert list(level0.c.values) == ["r", "g", "b"]
    assert level0.dtype == np.uint8
    assert level0.shape == (3, 64, 64)
    np.testing.assert_array_equal(level0.data.compute(), rgb.transpose(2, 0, 1))
    assert len(s["sample_he"]) == 2  # same pyramid depth as the store image
    assert isinstance(get_transformation(level0), Identity)
    assert s.attrs["cell_segmentation_image"] == "sample"


def test_records_the_registration(store, run_dir, tmp_path):
    import spatialdata as sd

    tif, _ = he_tif(tmp_path / "he.ome.tif")
    add_registered_image(store, tif, run_dir, "sample_he", "preprocessing/he_registration/sample")

    record = sd.read_zarr(store).attrs[ATTR]
    assert record["element"] == "sample_he"
    assert record["valis_pipeline"] == "v1.0.0"
    assert record["valis"] == "1.2.0"
    assert record["map_stage"] == "micro"
    assert record["um_per_px"] == {"if": 0.65, "he": 0.26}
    assert record["placement"] == {"method": "search", "gap": 0.31, "ambiguous": False}
    assert record["beyond_rigid_tissue_p99_um"] == pytest.approx(47.2)
    assert record["run"] == "preprocessing/he_registration/sample"


def test_another_size_fails_naming_both(store, run_dir, tmp_path):
    tif, _ = he_tif(tmp_path / "he.ome.tif", height=63)
    with pytest.raises(ValueError, match=r"63 x 64 px.*64 x 64 px"):
        add_registered_image(store, tif, run_dir, "sample_he", "x")


def test_a_rerun_replaces_the_element(store, run_dir, tmp_path):
    """A retried or resumed task meets the store it already mutated."""
    import spatialdata as sd

    tif, _ = he_tif(tmp_path / "he.ome.tif")
    add_registered_image(store, tif, run_dir, "sample_he", "x")
    add_registered_image(store, tif, run_dir, "sample_he", "x")
    assert sorted(sd.read_zarr(store).images) == ["sample", "sample_he"]
