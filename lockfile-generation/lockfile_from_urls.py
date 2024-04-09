#!/usr/bin/env python
import argparse
import collections
import json
import urllib.parse
from pathlib import Path
from typing import IO, Any, Iterable, NamedTuple


class ResolvedRPM(NamedTuple):
    arch: str
    repoid: str
    url: str

    def filename(self) -> str:
        return Path(urllib.parse.urlsplit(self.url).path).name


def gen_lockfile(rpms: Iterable[ResolvedRPM]) -> dict[str, Any]:
    arch_data: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"packages": [], "source": []}
    )

    for rpm in sorted(rpms):
        item = {"url": rpm.url, "repoid": rpm.repoid}
        if rpm.filename().endswith(".src.rpm"):
            arch_data[rpm.arch]["source"].append(item)
        else:
            arch_data[rpm.arch]["packages"].append(item)

    return {
        "lockfileVersion": 1,
        "lockfileVendor": "redhat",
        "arches": [{"arch": arch} | data for arch, data in arch_data.items()],
    }


def parse_rpms(input_file: IO[str]) -> Iterable[ResolvedRPM]:
    for line in input_file:
        arch, repoid, url = line.split()
        yield ResolvedRPM(arch=arch, repoid=repoid, url=url)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "input_file",
        type=argparse.FileType(),
        help="file that contains a list of {arch} {repoid} {url} triplets, one per line",
    )
    args = ap.parse_args()

    input_file: IO[str] = args.input_file

    lockfile = gen_lockfile(parse_rpms(input_file))
    print(json.dumps(lockfile, indent=2))


if __name__ == "__main__":
    main()
