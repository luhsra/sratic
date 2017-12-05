from jinja2 import Environment, FileSystemLoader
import operator
import re
import logging

class SRAticEnvironment(Environment):
    def __init__(self, template_dir):
        Environment.__init__(self, trim_blocks=True,
                             lstrip_blocks=True,
                             loader=FileSystemLoader([template_dir]))
        self.filters["expand"] = self.expand
        self.filters["warn"] = self.__warn
        self.filters["match"] = self.__match
        self.filters["search"] = self.__search

        self.filters["shorten"] = self.__shorten
        self.globals["str"] = repr
        self.globals["wrap_list"] = self.wrap_list
        self.globals["__id"] = id
        self.globals["operator"] = operator

        # This dict must never be overriden, the reference must be
        # kept intact at all times. It can only be cleared on each new page.
        self.globals['page'] = {}

        # A list of all copied and known assets
        self.assets = []
        self.globals['__asset'] = self.__asset

    def expand(self, text, **kwargs):
        # Some SRAtic specific markups
        # 1. Internal links

        def internal_link(m):
            obj = m.group(1)
            if m.group(2):
                link_attr = m.group(2)[1:] # Strip the dot
            else:
                link_attr = None
            if m.group(3) and m.group(3)[0] == ".":
                title_attr = m.group(3)[1:]
                title = None
            else:
                title = m.group(3)
                title_attr = None
            ret = "{{ nav.link(%s, title=%s, link_attr=%s, title_attr=%s) }}"%(
                    repr(obj), repr(title), repr(link_attr), repr(title_attr)
            )
            #logging.info(ret)

            return ret

        # [[OBJECT(.ATTR)?]([TITLE or .TITLE_ATTR])?]
        text = re.sub('\[\[([^\[\].]*?)((?:\.[^\[\]]*?)?)\](?:\[([^\[\]].*?)\])?\]', internal_link,
                         text)

        # 2. We always include show and navication, as it is used so often
        text = "{% import 'show.jinja'  as show %}" + \
               "{% import 'navigation.jinja'  as nav %}" + \
               "{% set R = page.relative_root %}" + \
               text

        template = self.from_string(text)
        return template.render(**kwargs)

    def wrap_list(self, elem):
        if type(elem) is self.undefined:
            return []
        if type(elem) is list:
            return elem
        return [elem]

    def __warn(self, text, **kwargs):
        logging.warning(text, **kwargs)
        return text

    def __shorten(self, elem, count):
        assert type(elem) is str
        if len(elem) < count:
            return elem
        return (elem[:count-1] + "&hellip;")


    def __regex(self, value='', pattern='', ignorecase=False, match_type='search'):
        if ignorecase:
            flags = re.I
        else:
            flags = 0
        _re = re.compile(pattern, flags=flags)
        return bool(getattr(_re, match_type)(str(value)))

    def __match(self, value, pattern='', ignorecase=False):
        return self.__regex(value, pattern, ignorecase, 'match')

    def __search(self,value, pattern='', ignorecase=False):
        return self.__regex(value, pattern, ignorecase, 'search')


    def __asset(self,name):
        found = None
        for asset in self.assets:
            if os.path.basename(asset) == name:
                assert found is None, "Asset %s is unambigous (%s,%s)" %(name, found, asset)
            found = asset
        return found
