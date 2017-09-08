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

        self.kv_store = {}
        self.globals['get'] = self.__kv_store_get
        self.globals['set'] = self.__kv_store_set


    def __kv_store_set(self, **kwargs):
        self.kv_store.update(kwargs)

    def __kv_store_get(self, key):
        return self.kv_store[key]

    def expand(self, text, **kwargs):
        # Some SRAtic specific markups
        # 1. Internal links
        def internal_link(m):
            link = m.group(1)
            title = m.group(2)
            if title:
                return "{{ nav.link(%s, title=%s) }}"%(
                    repr(link), repr(title)
                )
            return "{{ nav.link(%s) }}"%(repr(link))
        text = re.sub('\[\[([^\[\]].*?)\](?:\[([^\[\]].*?)\])?\]', internal_link,
                         text)

        # 2. We always include show and navication, as it is used so often
        text = "{% import 'show.jinja'  as show %}" + \
               "{% import 'navigation.jinja'  as nav %}" + \
               "{% set page = get('current_page') %}" + \
               "{% set R = get('relative_root') %}" + \
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
