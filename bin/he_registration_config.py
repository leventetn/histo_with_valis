#!/usr/bin/env python3
"""Write the valis_pipeline config for one REGISTER_HE task: the H&E onto Ashlar's stitched IF.

The image names are fixed (`if` reference, `he` moving), so valis_pipeline's step 5 writes
`spatialdata/he_on_if.ome.tif`. JSON is valid YAML, so the config needs no YAML library.
Standard library only: runs with the valis_pipeline image's Python.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# valis_pipeline's chosen setting for whole slides (its docs/decisions.md): rigid 1000 px,
# non-rigid 4000 px, DeepFlow. Not params: changing them needs a benchmark.
VALIS = {"processed_px": 1000, "non_rigid_px": 4000, "non_rigid": "deepflow"}
REFERENCE, MOVING = "if", "he"


def micro(value: str) -> str | float:
    """`native` or a number of µm greater than 0."""
    if value == "native":
        return value
    um = float(value)
    if um <= 0:
        raise ValueError(f"micro_um must be native or greater than 0, got {value}")
    return um


def build_config(
    name: str,
    ifimage: str,
    channel_index: int,
    heimage: str,
    placement: str,
    placement_check: str,
    micro_um: str,
) -> dict[str, Any]:
    """The run config; the run folder is ./<name>."""
    return {
        "name": name,
        "outdir": ".",
        "reference": {
            "name": REFERENCE,
            "path": str(Path(ifimage).absolute()),
            "channel_index": int(channel_index),
        },
        "moving": {"name": MOVING, "path": str(Path(heimage).absolute())},
        "placement": placement,
        "placement_check": placement_check,
        "micro_um": micro(micro_um),
        "same_section": True,
        "inverse": "invert",
        "spatialdata_mode": "none",
        "valis": dict(VALIS),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True, help="sample; the run folder")
    ap.add_argument("--if-image", required=True, help="Ashlar's stitched OME-TIFF")
    ap.add_argument("--channel-index", required=True, type=int, help="0-based nuclear channel of the IF")
    ap.add_argument("--he-image", required=True, help="H&E of the same section")
    ap.add_argument("--placement", default="search", choices=["search", "none"])
    ap.add_argument("--placement-check", default="stop", choices=["stop", "skip"])
    ap.add_argument("--micro-um", default="native")
    args = ap.parse_args()
    config = build_config(
        args.name,
        args.if_image,
        args.channel_index,
        args.he_image,
        args.placement,
        args.placement_check,
        args.micro_um,
    )
    print(json.dumps(config, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
