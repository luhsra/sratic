from jinja2 import Environment, FileSystemLoader
import operator
import re
import logging

def create_jinja2_env(template_dir):
    env = SRAticEnvironment(template_dir)

    return env

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


    def expand(self, text, **kwargs):
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
        return ""

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
