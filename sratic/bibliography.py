# coding: utf-8

import os.path as osp
import logging
import platform
import subprocess
import json
import sys

from pathlib import Path
from urllib import request

import yaml

from .metadata import Constructors

BIB2JSON_VERSION = ("0", "1", "0")


def resolve_load_bibtex(fragment, parent, key):
    fn, stmt_fn = parent[key][1]
    if type(fn) is list:
        # Serializing and reloading is the only possibility to
        # get a real dictionary from that YAML internal data structures.
        # fn[1] is the extra data
        modify_data = yaml.load(yaml.serialize(fn[1]), Loader=yaml.Loader)
        fn = fn[0].value
    else:
        modify_data = {}
    assert type(fn) is str, 'filename for !bibtex should be a string'
    fn = osp.join(osp.dirname(stmt_fn), fn)
    fragment.sources.add(fn)
    parent[key] = load_bibtex(fn, modify_data=modify_data)

Constructors.add("!bibtex", Constructors.LOAD_BIBTEX, resolve_load_bibtex)


def join_name(person):
    name = person['last_name']
    fn = person['first_name']
    if fn:
        name = fn + ' ' + name
    return name


def load_bibtex(filename, modify_data=None):
    """Loads a bibtex file, and exposes it as a dict, to be included by
       !bibtex.
    """
    filename = Path(filename)
    assert filename.exists(), f"{filename.absolute()} does not exist"

    bib2json = get_bib2json_path()
    json_bib = subprocess.run([bib2json, filename.absolute()],
                                check=True, capture_output=True)
    raw_bib = json.loads(json_bib.stdout)
    # a few things are different into sratic bibtex json and the one returned
    # by bib2json. Convert that.
    curated = {'entries': [],
               'keys': {},
               'years': {}}
    for entry in raw_bib.values():
        cur = {}
        for key, value in entry.items():
            if key == 'entry_type':
                cur['ENTRYTYPE'] = value
            elif key == 'id':
                cur['ID'] = value
                cur['id'] = 'bib:' + value
            elif key == 'authors':
                if value:
                    cur['authors'] = [join_name(x) for x in value]
            elif key == 'editors':
                if value:
                    cur['editors'] = [join_name(x) for x in value]
            elif key == 'type' and entry['entry_type'] == 'thesis':
                cur['thesistype'] = value
            else:
                cur[key] = value
        cur['type'] = 'bibtex'
        if modify_data:
            for k, v in modify_data.items():
                if k not in cur:
                    cur[k] = v
        curated['entries'].append(cur)
    return curated


def get_bib2json_path() -> Path | str:

    def version_compatible(path: Path | str) -> bool:
        try:
            version = subprocess.run(args=[path, "--version"], capture_output=True, text=True).stdout.strip()
            [major, minor, _] = version.split(" ")[1].split(".")
            logging.debug(f"bib2json version: {major}.{minor}")
            return (major, minor) == BIB2JSON_VERSION[0:2]
        except FileNotFoundError as e:
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
    except Exception as e:
        logging.error("Download of https://github.com/luhsra/bib2json failed")
        sys.exit(1)
    return exe_path


def download_bib2json(name: str, path: Path):
    path.parent.mkdir(exist_ok=True)
    version = ".".join(BIB2JSON_VERSION)
    url = f"https://github.com/luhsra/bib2json/releases/download/{version}/{name}"
    logging.info("GET " + url)
    request.urlretrieve(url, path)
    path.chmod(0o755)
