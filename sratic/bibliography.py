# coding: utf-8

import os.path as osp
import logging
import subprocess
import json
import sys

from pathlib import Path

import yaml

from .metadata import Constructors


def resolve_load_bibtex(fragment, parent, key):
    fn, stmt_fn = parent[key][1]
    if type(fn) is list:
        # Serializing and reloading is the only possibility to
        # get a real dictionary from that YAML internal data structrues.
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
    try:
        json_bib = subprocess.run(["bib2json", filename.absolute()],
                                  check=True, capture_output=True)
    except FileNotFoundError:
        logging.error("You need to install bib2json: https://github.com/luhsra/bib2json")
        sys.exit(2)
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
            else:
                if key not in ['pages', 'number'] and isinstance(value, str):
                    value = value.replace('---', '—')
                    value = value.replace('--', '–')
                    value = value.replace(r' \-', '').replace(r'\-', '')
                cur[key] = value
        cur['type'] = 'bibtex'
        if modify_data:
            for k, v in modify_data.items():
                if k not in cur:
                    cur[k] = v
        curated['entries'].append(cur)
    return curated
