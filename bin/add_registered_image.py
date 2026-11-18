#!/usr/bin/env python3
"""Add the H&E registered by valis_pipeline to a SpatialData store, on the store image's pixel grid.

valis_pipeline (spatialdata_mode none) writes the moved H&E as an RGB pyramid OME-TIFF with the
store image's height and width, so the element takes that image's transformations (Identity in
histo stores) and pyramid factors. Writes the `he_registration` store attribute from the run
folder; `cell_segmentation_image` is not changed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from project_channels import SEGMENTATION_ATTR, _levels, scale_factors_of

ATTR = "he_registration"
CHANNELS = ["r", "g", "b"]
# Image names written by he_registration_config.py; valis_pipeline names input files after them.
REFERENCE, MOVING = "if", "he"


def store_image(sdata: Any) -> str:
    """The image the H&E was registered onto: the segmentation image, else the only one."""
    name = sdata.attrs.get(SEGMENTATION_ATTR)
    if name is not None:
        return name
    candidates = [n for n in sdata.images if not n.endswith("_projected")]
    if len(candidates) != 1:
        raise ValueError(
            f"no '{SEGMENTATION_ATTR}' attribute and not one image element: {sorted(sdata.images)}"
        )
    return candidates[0]


def run_record(run_dir: Path, published: str) -> dict[str, Any]:
    """What the store records of the registration: versions, map, pixel sizes, placement, one QC number."""
    registration = json.loads((run_dir / "registration.json").read_text())
    provenance = json.loads((run_dir / "spatialdata" / "provenance.json").read_text())
    placement = json.loads((run_dir / "placement.json").read_text())
    stage = provenance["map_stage"]
    beyond_rigid = None
    with (run_dir / "qc" / "summary.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("stage") == stage and row.get("beyond_rigid_tissue_p99_um"):
                beyond_rigid = float(row["beyond_rigid_tissue_p99_um"])
                break
    return {
        "valis_pipeline": registration["code_version"],
        "valis": registration.get("versions", {}).get("valis-wsi"),
        "map_stage": stage,
        "um_per_px": {
            name: json.loads((run_dir / "inputs" / f"{name}.json").read_text())["um_per_px"]
            for name in (REFERENCE, MOVING)
        },
        "placement": {
            "method": placement.get("method"),
            "gap": placement.get("details", {}).get("gap"),
            "ambiguous": placement.get("ambiguous"),
        },
        "moving_covers_fraction": provenance.get("moving_covers_fraction"),
        "beyond_rigid_tissue_p99_um": beyond_rigid,
        "run": published,
    }


def add_registered_image(store: Path, tif: Path, run_dir: Path, name: str, published: str) -> dict[str, Any]:
    """Write `name` from `tif` into `store` and return the attribute written."""
    import dask.array as da
    import spatialdata as sd
    import tifffile
    import zarr
    from spatialdata.models import Image2DModel
    from spatialdata.transformations import get_transformation

    record = {"element": name} | run_record(run_dir, published)
    sdata = sd.read_zarr(store)
    source = store_image(sdata)
    levels = _levels(sdata[source])
    full = levels[0]
    shapes = [tuple(level.shape[1:]) for level in levels]

    with tifffile.TiffFile(tif) as tf:
        series = tf.series[0]
        if series.axes != "YXS" or series.shape[-1] != 3 or series.dtype != "uint8":
            raise ValueError(
                f"{tif}: expected an RGB uint8 image (axes YXS), got {series.axes} {series.shape} {series.dtype}"
            )
        if tuple(series.shape[:2]) != shapes[0]:
            raise ValueError(
                f"{tif} is {series.shape[0]} x {series.shape[1]} px, the store image '{source}' is "
                f"{shapes[0][0]} x {shapes[0][1]} px: the H&E must be on the store image's pixel grid"
            )
        rgb = da.from_zarr(zarr.open(series.aszarr(level=0), mode="r")).transpose(2, 0, 1)
        element = Image2DModel.parse(
            rgb,
            dims=("c", "y", "x"),
            c_coords=CHANNELS,
            transformations=get_transformation(full, get_all=True),
            scale_factors=scale_factors_of(shapes) or None,
            chunks=(3, *full.data.chunksize[1:]),
        )
        # A retried or resumed task meets the store it already mutated.
        if name in sdata.images:
            print(f"[add_registered_image] replacing '{name}' from an earlier attempt")
            del sdata[name]
            sdata.delete_element_from_disk(name)
        sdata[name] = element
        sdata.write_element(name)

    sdata.attrs[ATTR] = record
    sdata.write_attrs()
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdata", required=True, type=Path, help="SpatialData .zarr store")
    ap.add_argument("--image", required=True, type=Path, help="registered H&E, RGB pyramid OME-TIFF")
    ap.add_argument("--run", required=True, type=Path, help="valis_pipeline run folder")
    ap.add_argument("--element", required=True, help="name of the new image element")
    ap.add_argument("--published", required=True, help="where the run folder is published, for the record")
    args = ap.parse_args()

    record = add_registered_image(args.sdata, args.image, args.run, args.element, args.published)
    print(f"[add_registered_image] {args.sdata} :: {args.element}")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
