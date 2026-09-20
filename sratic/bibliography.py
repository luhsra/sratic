import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib import request

import yaml

from .metadata import YAMLLoader

BIB2JSON_VERSION = (0, 1, 2)


def resolve_load_bibtex(loader: YAMLLoader, node: yaml.Node) -> Any:
    value = loader.construct_any(node)
    logging.debug(f"Resolve bibtex {value}")
    match value:
        case [str(), dict()]:
            fn, modify_data = value
        case str():
            fn, modify_data = value, {}
        case _:
            raise ValueError(f"Invalid value for !bibtex: {value}")
    fn = Path(loader.path).parent / fn if loader.path else Path(fn)
    loader.add_source(fn)
    return load_bibtex(fn, modify_data=modify_data)


def fill_name(person: dict[str, str]) -> str:
    last = person["last_name"]
    first = person["first_name"]
    if first:
        return f"{first} {last}"
    return last


def censor_bibtex_entry(entry: str) -> str:
    blacklist = ["x-", "userd", "userc"]
    return "\n".join(
        [
            x
            for x in entry.split("\n")
            if not any(x.strip().startswith(m) for m in blacklist)
        ]
    )


def load_bibtex(
    filename: Path, modify_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Loads a bibtex file, and exposes it as a dict, to be included by
    !bibtex.
    """
    assert filename.exists(), f"{filename.absolute()} does not exist"

    bib2json = get_bib2json_path()
    json_bib = subprocess.run(
        [bib2json, filename.absolute()], check=True, capture_output=True
    )
    raw_bib: dict[str, dict[str, Any]] = json.loads(json_bib.stdout)
    # a few things are different into sratic bibtex json and the one returned
    # by bib2json. Convert that.
    curated = {"entries": [], "keys": {}, "years": {}}
    for entry in raw_bib.values():
        cur = {}
        for key, value in entry.items():
            if key == "entry_type":
                cur["ENTRYTYPE"] = value
            elif key == "id":
                cur["ID"] = value
                cur["id"] = "bib:" + value
            elif key == "authors":
                if value:
                    cur["authors"] = [fill_name(x) for x in value]
            elif key == "editors":
                if value:
                    cur["editors"] = [fill_name(x) for x in value]
            elif key == "type" and entry["entry_type"] == "thesis":
                cur["thesistype"] = value
            elif key == "bibtex":
                cur[key] = censor_bibtex_entry(value)
            else:
                cur[key] = value
        cur["type"] = "bibtex"
        if modify_data:
            for k, v in modify_data.items():
                if k not in cur:
                    cur[k] = v
        curated["entries"].append(cur)
    return curated


def get_bib2json_path() -> Path | str:
    def version_compatible(path: Path | str) -> bool:
        try:
            version = subprocess.check_output(
                args=[path, "--version"], text=True
            ).strip()
            [major, minor, patch] = [int(v) for v in version.split(" ")[1].split(".")]
            logging.debug("bib2json version: %s.%s.%s", major, minor, patch)
            return (major, minor) == BIB2JSON_VERSION[
                0:2
            ] and patch >= BIB2JSON_VERSION[2]
        except FileNotFoundError:
            return False

    # preinstalled bib2json
    exe_path = "bib2json"
    if version_compatible(exe_path):
        logging.debug("Use system bib2json")
        return exe_path

    # locally downloaded bib2json
    asset_name = {
        "Linux": "ubuntu-latest-bib2json",
        "Darwin": "macos-latest-bib2json",
        "Windows": "windows-latest-bib2json.exe",
    }.get(platform.system(), None)
    assert asset_name, "OS not supported"

    exe_path = Path(__file__).parent / "bin" / asset_name

    if version_compatible(exe_path):
        return exe_path

    try:
        download_bib2json(asset_name, exe_path)
    except OSError as e:
        logging.error("Download of bib2json failed: %s", e)
        sys.exit(1)
    return exe_path


def download_bib2json(name: str, path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    version = ".".join(map(str, BIB2JSON_VERSION))
    url = f"https://github.com/luhsra/bib2json/releases/download/{version}/{name}"
    logging.info("GET %s", url)
    request.urlretrieve(url, path)
    path.chmod(0o755)
