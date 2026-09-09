"""
A batch `esgpublish --map <directory>` run must attempt every mapfile
in the directory regardless of what happened to any earlier one --
neither an uncaught exception (missing .nc, corrupt file, etc.) nor a
graceful QC failure should stop the remaining files from being tried.

Exercised via real subprocess invocations of the actual `esgpublish`
console script (rather than importing main() directly and mocking
argparse/PubRunner), since the two real-world reproductions this fixes
were both found and confirmed that way against real mapfiles first.
"""
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import cftime
import numpy as np
import pytest

netCDF4 = pytest.importorskip("netCDF4")


def _write_minimal_nc(path, varname="tas"):
    ds = netCDF4.Dataset(str(path), "w")
    ds.createDimension("time", 2)
    time_var = ds.createVariable("time", "f8", ("time",))
    time_var.units = "days since 1850-01-01"
    time_var.calendar = "proleptic_gregorian"
    time_var[:] = [15.0, 45.0]
    var = ds.createVariable(varname, "f4", ("time",))
    var.standard_name = "air_temperature"
    var.units = "K"
    var[:] = [280.0, 281.0]
    ds.close()


def _write_mapfile(map_path, varname, nc_path, size=1000):
    dataset_id = (
        "MIP-DRS7.CMIP7.CMIP.Test-Institution.Test-Source.esm-hist."
        f"r1i1p1f1.glb.mon.{varname}.tavg-u-hxy-u.g100"
    )
    map_path.write_text(
        f"{dataset_id}.v20260101 | {nc_path} | {size} | mod_time=1700000000.0 "
        "| checksum=deadbeef | checksum_type=SHA256\n"
    )
    return dataset_id + ".v20260101"


def _run_esgpublish(map_dir, config_path):
    esgpublish = shutil.which("esgpublish") or str(
        Path(sys.executable).parent / "esgpublish"
    )
    return subprocess.run(
        [
            esgpublish,
            "--map",
            str(map_dir),
            "--project",
            "CMIP7",
            "--config",
            str(config_path),
            "--stac-api",
            "https://example.org/not-real",
            "--dry-run",
            "--save-stac",
            "--test",
            "--verbose",
        ],
        cwd=str(map_dir.parent),
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def batch_workdir(tmp_path):
    (tmp_path / "maps").mkdir()
    (tmp_path / "data").mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent(
            f"""\
            data_node: test.esgf.example
            data_roots:
              {tmp_path / "data"}: esg_dataroot
            autoc_path: none
            test: true
            disable_citation: true
            disable_further_info: true
            disable_qaqc: true
            verbose: true
            silent: false
            """
        )
    )
    return tmp_path, config


def test_missing_file_does_not_stop_the_batch(batch_workdir):
    tmp_path, config = batch_workdir
    data_dir = tmp_path / "data"
    maps_dir = tmp_path / "maps"

    good_a = data_dir / "aaa.nc"
    good_b = data_dir / "ccc.nc"
    missing = data_dir / "bbb_MISSING.nc"  # intentionally never created

    _write_minimal_nc(good_a, "aaa")
    _write_minimal_nc(good_b, "ccc")

    _write_mapfile(maps_dir / "1_aaa.map", "aaa", good_a)
    _write_mapfile(maps_dir / "2_bbb.map", "bbb", missing)
    _write_mapfile(maps_dir / "3_ccc.map", "ccc", good_b)

    result = _run_esgpublish(maps_dir, config)

    assert result.returncode == 1  # overall run did have a failure
    combined = result.stdout + result.stderr
    assert combined.count("Converting mapfile") == 3, combined
    assert "PUB_STATUS=PASS id=MIP-DRS7.CMIP7.CMIP.Test-Institution.Test-Source.esm-hist.r1i1p1f1.glb.mon.aaa." in combined
    assert "PUB_STATUS=PASS id=MIP-DRS7.CMIP7.CMIP.Test-Institution.Test-Source.esm-hist.r1i1p1f1.glb.mon.ccc." in combined
    assert "1 of 3 dataset(s) failed" in combined
    assert "FAILED: MIP-DRS7.CMIP7.CMIP.Test-Institution.Test-Source.esm-hist.r1i1p1f1.glb.mon.bbb." in combined
