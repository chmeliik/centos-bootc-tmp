#!/usr/bin/env python
import argparse
import hashlib
import json
import urllib.parse
from pathlib import Path


def sha256sum(filepath: Path) -> str:
    with open(filepath, "rb") as f:
        return f"sha256:{hashlib.file_digest(f, 'sha256').hexdigest()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lockfile_path", type=Path, default="rpms.lock.yaml", nargs="?")
    ap.add_argument("-d", "--cachi2-output-dir", type=Path, default="cachi2-output")
    args = ap.parse_args()

    lockfile_path: Path = args.lockfile_path
    cachi2_output_dir: Path = args.cachi2_output_dir

    with lockfile_path.open() as f:
        # NOTE: The lockfile can be yaml, but I don't want a 3rd party dep here. Let's assume
        #   the lockfile was generated with the lockfile_from_urls script, which writes it as json.
        lockfile = json.load(f)

    for arch_data in lockfile["arches"]:
        arch: str = arch_data["arch"]
        rpms = arch_data["packages"] + arch_data["source"]
        for rpm in rpms:
            repoid: str = rpm["repoid"]
            filename = Path(urllib.parse.urlsplit(rpm["url"]).path).name
            downloaded_rpm = cachi2_output_dir / "deps/rpm" / arch / repoid / filename

            if not rpm.get("size"):
                rpm["size"] = downloaded_rpm.stat().st_size
            if not rpm.get("checksum"):
                rpm["checksum"] = sha256sum(downloaded_rpm)

    with lockfile_path.open("w") as f:
        json.dump(lockfile, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
