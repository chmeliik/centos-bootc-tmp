#!/usr/bin/env python
import argparse
import collections
import configparser
import platform
import string
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Collection, Mapping, NewType, Self

URL = urllib.parse.SplitResult
RepoID = NewType("RepoID", str)


@dataclass(frozen=True)
class RepoSet:
    _mapping: Mapping[RepoID, Mapping[str, str]]

    @classmethod
    def parse_dir(cls, reposdir: Path) -> Self:
        repos: Mapping[RepoID, Mapping[str, str]] = {}

        for f in reposdir.iterdir():
            if f.is_file() and f.suffix == ".repo":
                repo = configparser.ConfigParser()
                repo.read(f)
                repos_in_file = (
                    (RepoID(section), attrs)
                    for section, attrs in repo.items()
                    if section != configparser.DEFAULTSECT
                )
                repos.update(repos_in_file)

        return cls(repos)

    def map_expanded_baseurls(self, arches: list[str]) -> dict[URL, RepoID]:
        mapping: dict[URL, RepoID] = {}
        for arch in arches:
            for repoid, attrs in self._mapping.items():
                baseurl = string.Template(attrs["baseurl"]).safe_substitute({"basearch": arch})
                mapping[urllib.parse.urlsplit(baseurl)] = repoid
        return mapping


def map_url_to_repoid(package_url: str | URL, baseurls_to_repoids: dict[URL, RepoID]) -> RepoID:
    if isinstance(package_url, str):
        package_url = urllib.parse.urlsplit(package_url)

    for baseurl, repoid in baseurls_to_repoids.items():
        if (
            package_url.scheme == baseurl.scheme
            and package_url.netloc == baseurl.netloc
            and Path(package_url.path).is_relative_to(Path(baseurl.path))
        ):
            return repoid

    raise ValueError(f"Couldn't find matching baseurl for {package_url.geturl()}")


def resolve_urls(
    packages: Collection[str], reposdir: Path, repoid: str, arch: str, source: bool
) -> list[str]:
    cmd = [
        "dnf",
        f"--setopt=reposdir={reposdir.resolve()}",
        f"--forcearch={arch}",
        "download",
        "--url",
    ]
    if not source:
        cmd.append(f"--repo={repoid}")
    else:
        # do not set --repo here, SRPMs may not always come from the expected repo
        cmd.append("--source")
    cmd.extend(packages)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if source:
            print(
                f"warning: couldn't get any SRPMs for the RPMs from {repoid!r}",
                file=sys.stderr,
            )
        print(proc.stderr, file=sys.stderr)
        if not source:
            proc.check_returncode()

    maybe_urls = proc.stdout.splitlines()
    return [url for url in maybe_urls if urllib.parse.urlsplit(url).scheme]


def parse_packages_per_repoid(input_file: IO[str]) -> dict[RepoID, list[str]]:
    packages_per_repoid: dict[RepoID, list[str]] = collections.defaultdict(list)
    for line in input_file:
        package, repoid = line.split()
        repoid = repoid.lstrip("(").rstrip(")")
        packages_per_repoid[RepoID(repoid)].append(package)
    return packages_per_repoid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "input_file",
        type=argparse.FileType(),
        help="file that contains a list of {package} ({repoid}) pairs, one per line",
    )
    ap.add_argument("--reposdir", type=Path, default=".")
    ap.add_argument("--arch", action="append")
    args = ap.parse_args()

    input_file: IO[str] = args.input_file
    reposdir: Path = args.reposdir
    arches: list[str] = args.arch or [platform.machine()]

    packages_per_repoid = parse_packages_per_repoid(input_file)
    baseurls_to_repoids = RepoSet.parse_dir(reposdir).map_expanded_baseurls(arches)

    for arch in sorted(arches):
        for repoid, packages in sorted(packages_per_repoid.items()):
            urls = sorted(resolve_urls(packages, reposdir, repoid, arch, source=False))
            source_urls = sorted(resolve_urls(packages, reposdir, repoid, arch, source=True))
            for url in urls + source_urls:
                repoid = map_url_to_repoid(url, baseurls_to_repoids)
                print(arch, repoid, url)


if __name__ == "__main__":
    main()
