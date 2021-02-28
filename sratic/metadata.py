# Metadata in SRAtic is stored as YAML. It can be contained directly
# in .yml files, or as a header within a page.

import yaml
from enum import Enum
import os.path as osp
import logging
import io
import os
import glob


class Constructors:
    INCLUDE = 1
    SPLICE  = 2
    LOAD_BIBTEX = 3
    PATH = 4
    MARKDOWN = 5


    handlers = {}

    @staticmethod
    def add(key, tag, fn):
        if tag in Constructors.handlers:
            return
        yaml.add_constructor(key, lambda loader, node: (tag, [node.value]))
        Constructors.handlers[tag] = fn

class YAMLFragment:
    def __init__(self, config):
        self.config = config
        self.sources = set()
        self.data  = None
        self.path  = None   # Absolute path to source file

    def __repr__(self):
        return "YAMLFragment('{}')".format(self.path)

    def __include_filename(self, data, fn):
        if type(data) is list:
            for elem in data:
                self.__include_filename(elem, fn)
        if type(data) is dict:
            for elem in data:
                self.__include_filename(data[elem], fn)
        if type(data) is tuple and data and data[0] in Constructors.handlers:
            data[1].append(fn)

    def load_from_file(self, filename):
        """Loads the data from the given source file into this YAML Fragment"""
        if not os.path.exists(filename):
            # Fallback to SRAtic provided files
            filename = os.path.join(os.path.dirname(__file__),
                                    "data",
                                    os.path.basename(filename))
        self.path = filename
        with open(filename) as stream:
            try:
                if filename.endswith(".myml"):
                    self.data = list(yaml.load_all(stream, Loader=yaml.Loader))
                else:
                    self.data = yaml.load(stream, Loader=yaml.Loader)
            except Exception as x:
                logging.error("Error in %s", filename)
                raise x

        self.__include_filename(self.data, filename)
        self.sources.add(filename)

    def load_from_string(self, text, origin_filename = None):
        self.path = origin_filename
        try:

            self.data = yaml.load(io.StringIO(text), Loader=yaml.Loader)
        except Exception as x:
            logging.error("Error in %s", origin_filename)
            raise x

        if origin_filename:
            self.__include_filename(self.data, origin_filename)
            self.sources.add(origin_filename)

    def load_nothing(self, origin_filename = None):
        self.path = origin_filename
        self.data = {}
        if origin_filename:
            self.__include_filename(self.data, origin_filename)
            self.sources.add(origin_filename)

    def objects(self):
        """Iterator over all objects"""
        visited = set()
        for prefix, k in  self.__objects(self.data, visited):
            yield k

    def __objects(self, x, visited, prefix = []):
        """A depth-first search through to reveal all objects in the object space."""
        if id(x) in visited:
            return
        visited.add(id(x))

        if type(x) is list:
            for idx, elem in enumerate(x):
                if type(elem) not in (list, dict):
                    continue
                for k in self.__objects(elem, visited, prefix + [idx]):
                    yield k

        elif type(x) is dict:
            if 'id' in x or 'type' in x:
                if not 'id' in x:
                    x['id'] = self.path + "-" + str(id(x))
                yield prefix, x

            for key, elem in x.items():
                if type(elem) not in (list, dict):
                    continue
                for k in self.__objects(elem, visited, prefix +[key]):
                    yield k

class YAMLDataFactory:
    def __init__(self, config):
        # Absolute filenames -> YAMLFragment
        self.__config = config
        self.__cache = {}

        # The !include constructor does insert the whole referenced
        # document instead of the field
        Constructors.add("!include", Constructors.INCLUDE,
                         self.__resolve_include)

        # The !splice tag is similar to !include, but merges the
        # referenced document into the parent node.
        Constructors.add("!splice", Constructors.SPLICE,
                         self.__resolve_splice)

        # The !path constructor
        Constructors.add("!path", Constructors.PATH,
                         self.__resolve_path)


    def __load_fragment(self, filename):
        """Load YAML Fragment, with caching. Fragments do not only originate
           in .yml files, but also pages can be given.

        """
        filename = osp.abspath(filename)
        if filename in self.__cache:
            return self.__cache[filename]
        # Load data file
        fragment = YAMLFragment(self.__config)
        if filename.endswith("yml"):
            fragment.load_from_file(filename)
        else:
            # Scrape data from file preface
            with open(filename) as fd:
                start = fd.read(3)
                if start == "---":
                    text = []
                    while True:
                        line = fd.readline();
                        if line is None or line.strip() == "---":
                            break
                        text.append(line)
                    fragment.load_from_string("".join(text), filename)
                else:
                    fragment.load_nothing(filename)
                ### Page Content
                fragment.data['page-body'] = fd.read()

            # Pages also read in their directory 'variables' file,
            # implicitly
            dirname = osp.dirname(filename)
            dir_file = osp.join(dirname, "variables.yml")
            if osp.exists(dir_file):
                if type(fragment.data) is list:
                    fragment.data.append( (Constructors.SPLICE, [dir_file, './IGNORE.yml']) )
                elif type(fragment.data) is dict:
                    fragment.data[object()] = (Constructors.SPLICE, [dir_file, './ignore.yml'])
                else:
                    sys.exit("YAML Type in %s is wrong (%s)"%(filename, type(fragment.data)))

        # Mark as placed in cache. Cannot be changed.
        self.__cache[filename] = fragment
        return fragment

    def load_file(self, filename):
        """Loads file, and resolves all external references. As a result, we
           get an newly created YAML Fragment."""

        ret = YAMLFragment(self.__config)
        ret.load_nothing(filename)
        ret.data = [(Constructors.INCLUDE, [filename, "./IGNORE.yml"])]
        again = True
        while again:
            ret, again = self.__resolve(ret, ret.data)

        ret.data = ret.data[0]
        if ret.data is None:
            ret.data = {}
        return ret

    ### Resolve Constructors
    def __resolve_splice(self, fragment, parent, key):
        fn, stmt_fn = parent[key][1]
        if '*' in fn:
            fns = glob.glob(osp.join(osp.dirname(stmt_fn), fn))
        else:
            fns = [fn]

        splice_data = None
        for fn in fns:
            fn = osp.join(osp.dirname(stmt_fn), fn)
            other = self.__load_fragment(fn)
            fragment.sources.update(other.sources)
            assert type(other.data) == type(parent),\
                "Splicing for %s failed. Type mismatch (%s != %s)"%(fn, type(other.data), type(parent))
            if splice_data is None:
                splice_data = other.data.copy()
            elif type(other.data) is dict:
                splice_data.update(other.data)
            else:
                splice_data += other.data

        if type(parent) is list:
            parent[key:key+1] = splice_data
        else:
            del parent[key]
            for k, v in splice_data.items():
                parent[k] = v
        return True

    def __resolve_include(self, fragment, parent, key):
        fn, stmt_fn = parent[key][1]
        fn = osp.join(osp.dirname(stmt_fn), fn)
        other = self.__load_fragment(fn)
        parent[key] = other.data
        fragment.sources.update(other.sources)
        return True

    def __resolve_path(self, fragment, parent, key):
        fn, stmt_fn = parent[key][1]
        if fn[0] == "/":
            parent[key] = fn
            return
        fn = osp.join(osp.dirname(stmt_fn), fn)
        fn = osp.relpath(fn, '.')
        parent[key] = "/" + fn

    def __resolve(self, fragment, x):
        """One depth-first search, to resolve constructors. Returns true, if
           this process has to be repeated.

        """
        handlers = Constructors.handlers
        again = False
        if type(x) is list:
            for idx, value in enumerate(x):
                if type(value) is tuple and value and value[0] in handlers:
                    if handlers[value[0]](fragment, x, idx):
                        again = True

                # Recursion
                if type(value) in (list, dict):
                    _, change = self.__resolve(fragment, value)
                    again = change or again
        elif type(x) is dict:
            for key, value in list(x.items()):
                if type(value) is tuple and value and value[0] in handlers:
                    if handlers[value[0]](fragment, x, key):
                        again = True
                # Recursion!
                if type(value) in (list, dict):
                    _, change = self.__resolve(fragment, value)
                    again = change or again
        return fragment, again
