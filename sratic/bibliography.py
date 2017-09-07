# coding: utf-8

import yaml
import re
import os.path as osp
from .metadata import Constructors
import bibtexparser
from collections import defaultdict


def resolve_load_bibtex(fragment, parent, key):
    fn, stmt_fn = parent[key][1]
    if type(fn) is list:
        # Serializing and reloading is the only possibility to
        # get a real dictionary from that YAML internal data structrues.
        # fn[1] is the extra data
        modify_data = yaml.load(yaml.serialize(fn[1]))
        fn = fn[0].value
    else:
        modify_data = {}
    assert type(fn) is str, 'filename for !bibtex should be a string'
    fn = osp.join(osp.dirname(stmt_fn), fn)
    fragment.sources.add(fn)
    parent[key] = load_bibtex(fn, modify_data=modify_data)

Constructors.add("!bibtex", Constructors.LOAD_BIBTEX, resolve_load_bibtex)

def load_bibtex(filename, modify_data=None):
    """Loads a bibtex file, and exposes it as a dict, to be included by
       !bibtex.
    """
    fd = open(filename)
    parser = bibtexparser.bparser.BibTexParser()
    parser.ignore_nonstandard_types = False
    data = bibtexparser.load(fd, parser)
    ret = {
        'entries': [],
        'years': defaultdict(list),
        'keys': {}
    }
    by_id = {e['ID']: e for e in data.entries}
    for e in data.entries:
        # Update Data with the modify data from the !bibtex command,
        # to supply default values.
        if modify_data:
            for k, v in modify_data.items():
                if not k in e:
                    e[k] = v
        # Resolve crossref
        if 'crossref' in e:
            assert e['crossref'] in by_id,\
                "Crossref %s could not be resolved" %( e['crossref'])
            cr = by_id[e['crossref']]
            # Copy all keys that are not defined into the entry
            for key in cr:
                if not key in e:
                    e[key] = cr[key]
            del e['crossref']
        # Generate pretty printed bibtex entry for inclusion into pages.
        db = bibtexparser.bibdatabase.BibDatabase()
        ee = dict(e)
        for key in [x for x in ee.keys() if x.startswith('x-')]:
            del ee[key]
        db.entries = [ee]
        e['bibtex'] = bibtexparser.dumps(db).strip()
        e['id'] = 'bib:' + e['ID']
        e['type'] = 'bibtex'

        if 'year' not in e['bibtex']:
            logging.warning("Bibtex Entry %s has no year field",  e['id'])

        # ATTENTION: We ignore proceedings entries
        if e['ENTRYTYPE'].lower() == 'proceedings':
            continue

        ret['entries'].append(e)

        # Normalize Fields
        for field in ('title', 'author','booktitle', 'editor', 'school', 'publisher', 'note', 'x-award'):
            if field not in e:
                continue
            tmp = e[field]
            replace = {r'\ss': 'ß', r"\#": "#",
                       r'\"{a}': 'ä', r'\"a': 'ä',
                       r'\"{u}': 'ü', r'\"u': 'ü',
                       r'\"{o}': 'ö', r'\"o': 'ö',
                       r"\'{a}": 'á', r"\'a": 'á',
                       r"\'{e}": 'é', r"\'e": 'é',
                       r"\'{E}": 'É', r"\'E": 'É',
                       '\&': '&',
                       '\-': '',
                       '---': '––',
                       '--': '–',
                       '\\textendash': '–',
                       '\n': ' ',
                       '\r': ' ' }
            for k,v in replace.items():
                tmp = tmp.replace(k,v)
            regex_repl = [('\\\\emph{([^{}]*)}', '<it>\\1</it>'),
                          ('{([^{}]*)}', '\\1')]
            for k,v in regex_repl:
                tmp = re.sub(k, v, tmp)


            e[field] = tmp

        for field in ('author', 'editor'):
            if field not in e:
                continue

            field_p = field + "s"
            e[field_p] = [x.strip() for x in e[field].replace('\n', ' ').split(' and ')]
            for i, a in enumerate(e[field_p]):
                if ',' in a:
                    a = a.split(',', 1)
                    e[field_p][i] = ("%s %s" % (a[1], a[0])).strip()


    fd.close()
    return ret
