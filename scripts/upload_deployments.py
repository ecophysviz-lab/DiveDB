#!/usr/bin/env python3
"""Upload pyologger-exported netCDFs to DiveDB's Iceberg storage.

The script form of docs/upload_docs.ipynb, for batch runs.

Two independent switches select the source and destination, mirroring the
notebook: netCDFs come from a local directory or an s3:// prefix, and the
warehouse is a local path or an s3:// prefix. Both default to the values in the
repo-root .env.

Examples:
    # What is available, and what is already in the warehouse
    upload_deployments.py --list mile-adult-sese_vdr_argentina_RD-KM

    # Resolve paths and check existence, without uploading
    upload_deployments.py --dataset <ds> --deployments <dep> <dep> --dry-run

    # Every deployment in a dataset that is not already uploaded
    upload_deployments.py --dataset <ds> --all --skip-uploaded

    # Explicit pairs across datasets
    upload_deployments.py --pair <ds> <dep> --pair <ds2> <dep2>

Credentials are read from the environment and never printed.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import xarray as xr
from dotenv import load_dotenv

from DiveDB.services.data_uploader import DataUploader
from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager

# Notion databases keyed by the display name NotionORMManager expects. IDs come from
# NOTION_DB_<NAME>, the convention shared with pyologger and EcoPhysVideoViz.
NOTION_DB_MAP = {
    "Deployment DB": "NOTION_DB_DEPLOYMENT",
    "Recording DB": "NOTION_DB_RECORDING",
    "Logger DB": "NOTION_DB_LOGGER",
    "Animal DB": "NOTION_DB_ORGANISM",
    "Dataset DB": "NOTION_DB_DATASET",
    "Signal DB": "NOTION_DB_SIGNAL",
    "Standardized Channel DB": "NOTION_DB_STANDARDIZED_CHANNEL",
    "Procedure DB": "NOTION_DB_PROCEDURE",
    "Observation DB": "NOTION_DB_OBSERVATION",
    "Collaborator DB": "NOTION_DB_COLLABORATOR",
    "Location DB": "NOTION_DB_LOCATION",
    "Montage DB": "NOTION_DB_MONTAGE",
    "Attachment DB": "NOTION_DB_ATTACHMENT",
    "Original Channel DB": "NOTION_DB_ORIGINAL_CHANNEL",
    "Species DB": "NOTION_DB_SPECIES",
    "Assets DB": "NOTION_DB_ASSET",
}


def repo_root_env() -> Path:
    """The EcoViz_DiveDB repo-root .env, never the DiveDB/ submodule copy.

    find_dotenv() stops at the nearest .env, which differs by working directory;
    the root file is the single source of truth.
    """
    for parent in [Path.cwd(), *Path.cwd().parents]:
        if parent.name == "EcoViz_DiveDB":
            return parent / ".env"
    raise RuntimeError(
        f"Not running inside EcoViz_DiveDB (cwd={Path.cwd()}); cannot locate root .env."
    )


class Uploader:
    """Resolves source/destination and uploads deployments."""

    def __init__(
        self, use_local_nc: bool, use_local_iceberg: bool, quiet: bool = False
    ):
        self.env_path = repo_root_env()
        if not self.env_path.exists():
            raise RuntimeError(f"No .env at {self.env_path}")
        load_dotenv(self.env_path, override=True)

        self.use_local_nc = use_local_nc
        self.use_local_iceberg = use_local_iceberg

        self.data_root = (
            self._env("LOCAL_DATA_PATH") if use_local_nc else self._env("S3_DATA_PATH")
        )

        # WarehouseConfig selects the S3 backend whenever S3_ENDPOINT is set, so a
        # local warehouse must withhold the S3 kwargs rather than merely ignore them.
        if use_local_iceberg:
            self.warehouse_path = self._env("LOCAL_ICEBERG_PATH")
            kwargs = {"warehouse_path": self.warehouse_path}
        else:
            self.warehouse_path = self._env("S3_WAREHOUSE_PATH")
            kwargs = {
                "warehouse_path": self.warehouse_path,
                "s3_endpoint": self._env("S3_ENDPOINT"),
                "s3_access_key": self._env("S3_ACCESS_KEY"),
                "s3_secret_key": self._env("S3_SECRET_KEY"),
            }

        if not quiet:
            self._print_route()

        db_map = {n: os.getenv(v) for n, v in NOTION_DB_MAP.items()}
        unset = sorted(n for n, v in db_map.items() if not v)
        db_map = {n: v for n, v in db_map.items() if v}
        if unset and not quiet:
            print(f"Notion databases skipped (env var unset): {', '.join(unset)}")

        notion = NotionORMManager(token=os.getenv("NOTION_TOKEN"), db_map=db_map)
        self.duck_pond = DuckPond(**kwargs, notion_manager=notion)
        self.data_uploader = DataUploader(duck_pond=self.duck_pond)

    def _env(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"{name} is not set. Add it to {self.env_path}.")
        return value

    def _print_route(self) -> None:
        wh = self.warehouse_path.rstrip("/")
        print(f"config from       : {self.env_path}")
        print()
        print(f"Iceberg warehouse : {wh.rsplit('/', 1)[-1]}")
        print(f"  inside          : {wh.rsplit('/', 2)[-2] if '/' in wh else ''}")
        print(f"  full path       : {wh}")
        print(
            f"  backend         : "
            f"{'local disk' if self.use_local_iceberg else 'Ceph S3'}"
        )
        print()
        print(f"Will upload data FROM : {self.data_root}")
        print(f"                   TO : {self.warehouse_path}")
        print(
            f"        netCDF source : "
            f"{'local disk' if self.use_local_nc else 'Ceph S3'}"
        )
        print()

    # --- source resolution ---------------------------------------------------

    def nc_path(self, dataset_id: str, deployment_id: str) -> str:
        return (
            f"{self.data_root}/{dataset_id}/{deployment_id}"
            f"/outputs/{deployment_id}_output.nc"
        )

    def _fs(self):
        import s3fs

        return s3fs.S3FileSystem(
            key=os.environ["S3_ACCESS_KEY"],
            secret=os.environ["S3_SECRET_KEY"],
            client_kwargs={"endpoint_url": os.environ["S3_ENDPOINT"]},
        )

    def nc_exists(self, path: str) -> bool:
        if self.use_local_nc:
            return Path(path).exists()
        return self._fs().exists(path.replace("s3://", ""))

    def available_deployments(self, dataset_id: str) -> list[str]:
        if self.use_local_nc:
            root = Path(self.data_root) / dataset_id
            if not root.is_dir():
                return []
            names = sorted(p.name for p in root.iterdir() if p.is_dir())
        else:
            fs = self._fs()
            prefix = f"{self.data_root}/{dataset_id}".replace("s3://", "")
            if not fs.exists(prefix):
                return []
            names = sorted(p.rstrip("/").split("/")[-1] for p in fs.ls(prefix))
        return [n for n in names if self.nc_exists(self.nc_path(dataset_id, n))]

    def uploaded_deployments(self, dataset_id: str) -> list[str]:
        try:
            table = self.duck_pond.catalog.load_table(f"{dataset_id}.data")
        except Exception:
            return []  # dataset not in the warehouse yet
        found = set()
        for f in table.inspect.files().to_pylist():
            for part in f["file_path"].split("/"):
                if part.startswith("deployment="):
                    found.add(part.split("=", 1)[1])
        return sorted(found)

    # --- upload --------------------------------------------------------------

    def upload(self, dataset_id: str, deployment_id: str, src: str) -> None:
        with xr.open_dataset(src) as ds:
            organism_id = ds.attrs["animal_info_Animal_ID"]
            logger_ids = sorted(
                {
                    str(v).strip()
                    for k, v in ds.attrs.items()
                    if "logger_id" in k.lower() and v
                }
            )

        # A pyologger export holds ALL of a deployment's loggers in one merged file,
        # so it is uploaded once. Looping over logger_ids would re-upload the whole
        # file per logger and duplicate every row.
        recording = f"{deployment_id}_{organism_id}"
        if len(logger_ids) == 1:
            recording = f"{recording}_{logger_ids[0]}"

        print(f"  loggers: {', '.join(logger_ids) or 'none listed'}")
        print(f"  -> {recording}", flush=True)
        self.data_uploader.upload_netcdf(
            src,
            {
                "dataset": dataset_id,
                "organism": organism_id,
                "deployment": deployment_id,
                "recording": recording,
            },
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--list",
        metavar="DATASET",
        nargs="+",
        help="list available vs already-uploaded deployments and exit",
    )
    ap.add_argument("--dataset", help="dataset id for --deployments / --all")
    ap.add_argument("--deployments", nargs="+", default=None)
    ap.add_argument(
        "--all",
        action="store_true",
        help="every deployment in --dataset that has a netCDF",
    )
    ap.add_argument(
        "--pair",
        nargs=2,
        action="append",
        metavar=("DATASET", "DEPLOYMENT"),
        help="explicit dataset/deployment pair; repeatable",
    )
    ap.add_argument(
        "--skip-uploaded",
        action="store_true",
        help="skip deployments already in the warehouse",
    )
    ap.add_argument(
        "--s3-nc",
        action="store_true",
        help="read netCDFs from S3_DATA_PATH instead of LOCAL_DATA_PATH",
    )
    ap.add_argument(
        "--local-iceberg",
        action="store_true",
        help="write to LOCAL_ICEBERG_PATH instead of S3_WAREHOUSE_PATH",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve and check paths without uploading",
    )
    args = ap.parse_args()

    up = Uploader(
        use_local_nc=not args.s3_nc,
        use_local_iceberg=args.local_iceberg,
    )

    if args.list:
        for ds in args.list:
            available = up.available_deployments(ds)
            uploaded = set(up.uploaded_deployments(ds))
            new = [d for d in available if d not in uploaded]
            print(f"{ds}")
            print(
                f"  netCDFs found: {len(available)}   "
                f"({len(new)} new, {len(available) - len(new)} already uploaded)"
            )
            for dep in available:
                mark = "[uploaded]" if dep in uploaded else "[   new  ]"
                print(f"    {mark}  {dep}")
            missing = sorted(uploaded - set(available))
            if missing:
                print(f"  in the warehouse but no netCDF here: {', '.join(missing)}")
            print()
        return 0

    pairs: list[tuple[str, str]] = []
    if args.pair:
        pairs += [(d, p) for d, p in args.pair]
    if args.dataset:
        if args.all:
            pairs += [(args.dataset, d) for d in up.available_deployments(args.dataset)]
        elif args.deployments:
            pairs += [(args.dataset, d) for d in args.deployments]
        else:
            ap.error("--dataset requires --all or --deployments")
    if not pairs:
        ap.error("nothing to do: pass --list, --pair, or --dataset")

    if args.skip_uploaded:
        cache: dict[str, set[str]] = {}
        kept = []
        for ds, dep in pairs:
            if ds not in cache:
                cache[ds] = set(up.uploaded_deployments(ds))
            if dep in cache[ds]:
                print(f"[SKIP   ] {ds}/{dep} (already uploaded)")
            else:
                kept.append((ds, dep))
        pairs = kept

    ready = []
    for ds, dep in pairs:
        src = up.nc_path(ds, dep)
        exists = up.nc_exists(src)
        print(f"[{'OK     ' if exists else 'MISSING'}] {ds}/{dep}")
        print(f"          FROM {src}")
        print(f"          TO   {up.warehouse_path}/{ds}.db/data")
        if exists:
            ready.append((ds, dep, src))

    print(f"\n{len(ready)} of {len(pairs)} ready to upload")
    if args.dry_run:
        print("(dry run: nothing uploaded)")
        return 0

    ok, failed = [], []
    for i, (ds, dep, src) in enumerate(ready, 1):
        print(f"\n[{i}/{len(ready)}] {ds}/{dep}", flush=True)
        t0 = time.time()
        try:
            up.upload(ds, dep, src)
            print(f"  done in {time.time() - t0:.0f}s", flush=True)
            ok.append(dep)
        except Exception as exc:  # keep going; report at the end
            print(f"  FAILED: {type(exc).__name__}: {exc}", flush=True)
            failed.append((dep, f"{type(exc).__name__}: {exc}"))

    print("\n" + "=" * 66)
    print(
        f"uploaded: {len(ok)}   failed: {len(failed)}   "
        f"missing: {len(pairs) - len(ready)}"
    )
    for dep, err in failed:
        print(f"  FAILED {dep}: {err[:120]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
