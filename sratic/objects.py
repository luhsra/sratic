# coding: utf-8

from .schema import schema_for_obj, check_schema
import os.path as osp
import datetime
import hashlib
import base64
import re
import logging
import uuid

def wrap_list(lst):
    if not lst:
        return []
    if type(lst) != list:
        return [lst]
    return lst

class ObjectStore:
    def __init__(self):
        self.objects = {}
        self.schema = None

        self.object_constructors = {
            'lecture': self.__init__lecture,
            'thesis': self.__init__thesis,
        }

        # We keep a pointer to the current set of referenced objects
        self.__referenced_objects = None

    def set_referenced_objects(self, x):
        """The user can set a dictionary that is filled with id -> hash while using deref and object.list()"""
        self.__referenced_objects = x

    def __reference(self, obj):
        """Mark the object as referenced"""
        if self.__referenced_objects is not None and obj.get('id'):
            self.__referenced_objects.add(obj['id'])

    def canonical_id(self, obj):
        """Canonical ascii-only id for use in CSS classes"""
        ret=""
        for c in obj['id']:
            if c.isalpha():
                ret += c
            else:
                ret += str(ord(c))
        return ret

    def schema_for(self, obj):
        return schema_for_obj(self.schema, obj)

    def crawl_pages(self, schema, data_dir, pages):
        # The dict that maps every object id to its object
        # ID -> object
        objects = self.objects
        self.schema = schema

        # ID -> YAMLFragment
        page_objects = {}

        aliases = {}

        # Step 1: Every page object should have an ID. If it does not
        # have an ID, we assign the local part of the page as an id. E.g.
        # `/index.html' for the root page
        for page in pages:
            (base, ext) = osp.splitext(page.path)
            page.data['href'] = base[1:] + ".html"
            if "id" in page.data:
                perma_name =  page.data['id'].replace(':', '__')
                page.data['permalink.href'] = '/p/' + perma_name
            else:
                page.data['id'] = page.data['href']


            # Step 1.1: include all objects in this page to the object
            # index.
            for obj in page.objects():
                objects[obj['id']] = obj
                obj['__file__'] = page.path
            # Step 1.2: build an index of all page yaml fragments
            assert page.data['id'] not in page_objects, \
                "Duplicate Page ID: %s" % page.data['id']
            page_objects[page.data['id']] = page

            # Step 1.3: Add the page type to the page
            Type = ['page']
            if 'type' in page.data:
                if type(page.data['type']) is list:
                    Type += page.data['type']
                else:
                    assert type(page.data['type']) is str
                    Type += [page.data['type']]
            page.data['type'] = Type

            # Step 1.4: Sanity check aliases
            if page.data['id'] in data_dir.data.get('permalinks', {}):
                assert 'permalink.alias' not in page.data, "Page %s (%s): global permalink alias conflicts with page-local permalink.alias. Remove either one" % (page.data['id'], page.data['__file__'])
                page.data['permalink.alias'] = data_dir.data['permalinks'][page.data['id']]
            if 'permalink.alias' in page.data:
                alias = page.data['permalink.alias']
                assert alias not in aliases, "Alias %s is duplicated: %s, %s" % (alias, page.data['__file__'],
                                                                             aliases[alias].data['__file__'])
                aliases[alias] = page
                page.data['permalink.alias.href'] = 'p/' + alias


        # Step 2: Generate an Index for all objects that are defined in the data directory
        for obj in data_dir.objects():
            assert obj['id'] not in objects, "Duplicate Object ID (%s)" %(obj['id'])
            objects[obj['id']] = obj
            obj['__file__'] = data_dir.path

            if 'object_aliases' in obj:
                for alias in obj['object_aliases']:
                    assert alias not in objects, \
                        "Alias (object_aliases) %s is duplicated" % (alias)
                    objects[alias] = obj

        # Step 3: Generate publication object, if they are not present.
        for obj in list(objects.values()):
            if self.isA(obj, 'bibtex'):
                if obj['ID'] in objects:
                    page = objects[obj['ID']]
                else:
                    # Generate a surrogate publication object
                    page = {'id': obj['ID'], 'type': 'publication',
                            '__file__': obj['__file__']}
                    obj['__surrogate_object'] = page
                    objects[page['id']] = page

                # Update some fields from the bibtex entry
                page['bibtex'] = obj
                page['x-exported'] = obj.get('x-exported', True)
                if not 'title' in page:
                    page['title'] = obj['title']
                # Extract list of projects from bibtex file
                page['projects'] = list(filter(None, [x.strip() for x in obj.get('x-projects','').split(",")]))

        for k, transform in data_dir.data.get('bibliography', {}).items():
            if not k.startswith('transform-'):
                continue
            for obj in self.object_list('publication', **transform['filter']):
                obj['bibtex'].update(transform['set'])

        # Step 4: Adjust types and run constructors
        for obj in objects.values():
            # Wrap type field
            if type(obj['type']) == str:
                obj['type'] = [obj['type']]

            for T in obj['type']:
                if T in self.object_constructors:
                    self.object_constructors[T](obj)
        # Step 8: Generate alias IDs for some objects
        for obj in list(objects.values()):
            aliases = []
            if self.isA(obj, 'person') and obj['name'] not in objects:
                aliases.append(obj['name'])

            # Permalink aliases provoke an object alias
            if 'permalink.alias' in obj:
                aliases.append(obj['permalink.alias'])
                obj['permalink.alias.href'] = "/p/" + obj['permalink.alias']

            for id in aliases:
                if id in objects:
                    assert obj == objects[id],\
                        "Duplicate object ID: %s" %(id)
                else:
                    objects[id] = obj

        # Step 5: Assemble the sitemap and the parent->child relation
        for obj in objects.values():
            if 'parent' in obj:
                p = obj['id']
                pp = obj['parent']
                assert obj['parent'] in objects, \
                    "Parent %s is unknown (in %s)"%(pp, obj["id"])
                # Add the page ID to the children, not the actual data
                if not 'children' in objects[pp]:
                    objects[pp]['children'] = []
                if not p in objects[pp]['children']:
                    objects[pp]['children'].append(p)

                # Add dependencies
                if not 'depends' in objects[pp]:
                    objects[pp]['depends'] = []
                if type(objects[pp]['depends']) is str:
                    objects[pp]['depends'] = [objects[pp]['depends']]
                objects[pp]['depends'].append(p)

                # Add dependencies
                if p in page_objects and pp in page_objects:
                    page_objects[pp].sources.add(page_objects[p].path)
            # Subsume all mentioned children, if they have no parent
            for child in obj.get('children', []):
                if type(child) is str:
                    child = objects.get(child)
                    if child and 'parent' not in child:
                        child['parent'] = obj['id']

        # Step 5b: Assemble submenu structures if submenu.list is set True
        for obj in objects.values():
            if 'parent' in obj and obj.get('submenu.list',False):
                p = obj['id']
                pp = obj['parent']
                if not 'submenu' in objects[pp]:
                    objects[pp]['submenu'] = []
                if not p in objects[pp]['submenu']:
                    objects[pp]['submenu'].append(p)


            # Wrap the dependencies, when we're at it
            # Then this works also
            #   depends: main
            if 'depends' in obj:

                obj['depends'] = wrap_list(obj['depends'])


        # Step 6: Validate the schema for all objects, we are aware of.
        for obj in objects.values():
            # Do a schema validation for the page data
            check_schema(schema, obj, self)


        # Step 7: Resolve and propagate all dependencies between objects.
        changed = True
        while changed:
            changed = False
            for obj in objects.values():
                if 'depends' in obj:
                    deps = set(obj['depends'])
                    old = len (deps)
                    for other in list(deps):
                        assert other in objects, "Dependency %s is unknown" %(
                            other)
                        deps.update(objects[other].get('depends', []))
                    # And maybe again
                    changed = changed or old != len(deps)
                    obj['depends'] = deps
        for page in pages:
            for other in page.data.get('depends', []):
                if other in page_objects:
                    page.sources.update(page_objects[other].sources)


        self.objects = objects
        logging.info("%d pages, %d objects", len(page_objects),
                     len(self.objects))

        # Step 9: For each page, find the page that holds its menu and
        # add an according dependency
        for page in pages:
            p = page
            while p:
                if self.has_menu_children(p.data):
                    page.sources.add(p.path)
                    break
                if 'submenu' in p.data:
                    page.sources.add(p.path)
                # Search in parent
                if 'parent' not in p.data:
                    break
                else:
                    pp = p.data['parent']
                    ## resolve alias
                    if pp not in page_objects:
                        pp = objects[pp]['id']
                    p = page_objects[pp]

    def has_menu_children(self, elem):
        entries = self.deref(elem).get('menu') or self.deref(elem).get('children', [])
        for p in entries:
            p = self.deref(p)
            if p.get('menu.list', True) and not p.get('submenu.list', False):
                return True
        return False

    def is_child_of(self, elem, parent):
        p = self.deref(parent)
        x = self.deref(elem)
        while x:
            if x == p:
                return True
            if x.get('parent') in self.objects:
                x = self.deref(x.get('parent'))
            else:
                break
        return False

    def teaching_sose ( self, elem ):
        return elem.startswith("lehre-ss")

    def teaching_wise ( self, elem ):
        return elem.startswith ("lehre-ws")

    @staticmethod
    def __init__lecture(obj):
        """For a lecture we fill semester, series and parent from the ID"""
        regex = '^lehre-([ws]s[0-9]{2})-([A-Z??????_]+)$'
        m = re.match(regex, obj['id'])
        assert m, "Invalid id for lecture, use: " + regex
        semester, series = m.groups()
        obj['semester'] = semester
        obj['sortkey'] = semester[2:]+semester[:2]
        obj['semester-pretty'] = ("Sommer" if semester[0] == 's' else "Winter") + " 20" + semester[2:]
        obj['series'] = series
        obj['parent'] = 'lehre-' + semester
        obj['modkat'] = 'modkat-' + semester + '-' + series

    @staticmethod
    def __init__thesis(obj):
        """For a thesis we fill the year from the parent directory, if not explicitly set"""
        if 'thesis-end' in obj:
            obj['thesis-year'] = str(obj['thesis-end'].year)
        elif 'thesis-start' in obj:
            obj['thesis-year'] = str(obj['thesis-start'].year)
        else:
            obj['thesis-year'] = osp.basename(osp.dirname(obj['__file__']))

    def get_submenu(self, page):
        """Search for the first parent with a submenu.

        Return the submenu as a list. If no such page is found, an empty list
        is returned.

        Arguments:
        page -- the current page
        """
        p = self.deref(page)
        while p:
            if 'submenu' in p:
                return p['submenu']
            if p.get('parent') in self.objects:
                p = self.deref(p.get('parent'))
            else:
                break
        return []

    @staticmethod
    def get_rfc3339_timestamp():
        """Return an RFC 3339 timestamp.

        Note, this works only with Python 3.3+.
        """
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        return now.isoformat()

    @staticmethod
    def uuid(text):
        """A Jinja Filter that creates an UUID
        """
        return uuid.uuid5(uuid.NAMESPACE_URL, text)


    def deref(self, elem, fail=True):
        """Dereferences a object, if it should be necessary"""
        if type(elem) is dict:
            self.__reference(elem)
            return elem
        elif elem in self.objects:
            obj = self.objects[elem]
            self.__reference(obj)
            return obj
        elif fail:
            raise RuntimeError("Object '{}' not found".format(elem))

    def isA(self, obj, Type):
        assert type(Type) is str
        if obj.get('type', None) == Type:
            return True
        if type(obj.get('type')) is list:
            return Type in obj['type']
        return False

    def object_unique(self, objs):
        ids = set()
        ret = []
        for obj in objs:
            if type(obj) is str:
                id = obj
            else:
                id = obj['id']
            if id not in ids:
                ret.append(obj)
            ids.add(id)
        return ret



    def object_list(self, type,
                    filter=None,
                    status=None,
                    supervisor=None,
                    project=None,
                    author=None,
                    own=None,
                    bibtype=None,
                    entrysubtype=None,
                    award=None,
                    core=None,
                    maxage=None,
                    show_list=False,
                    is_alias=None,
                    lecture=None,
                    staff=None,
                    semester=None,
                    studygroup=None,
                    series=None,
                    ):
        ret = []
        captured = set()

        for _id, obj in self.objects.items():
            if self.isA(obj, type) \
            and (obj.get('show.list', 'true') or show_list) \
            and (not filter or eval(filter)(obj)) \
            and (is_alias is None or is_alias == bool(obj.get('permalink.alias'))) \
            and ((
                type == 'thesis'
                and (not status or obj['thesis-status'] in status)
                and (not supervisor or supervisor in obj['thesis-supervisor'])
                and (not project or project in obj['projects'])
            ) or (
                type == 'project'
                and (not status or obj['project-status'] in status)
            ) or (
                type == 'news'
                and (not project or ('related' in obj and project in obj['related']))
                and (not maxage or (datetime.date.today() - obj['date']).days < obj.get('maxage', maxage))
            ) or (
                type == 'publication'
                and (not project or project in obj['projects'])
                and (own == None or own == obj['bibtex'].get('x-own', False))
                and (not bibtype or obj['bibtex']['ENTRYTYPE'].lower() in wrap_list(bibtype))
                and (not entrysubtype or obj['bibtex'].get('entrysubtype') in wrap_list(entrysubtype))
                and (not award  or obj['bibtex'].get('x-award'))
                and (not core or (obj['bibtex'].get('userc') and obj['bibtex'].get('userc').split(":")[1] in wrap_list(core)))
                and (not author or (author in (obj['bibtex'].get('authors',[]) \
                                            + obj['bibtex'].get('editors',[]))))
            ) or (
                type == 'person'
            ) or (
                type == 'evaluation'
                and (not lecture or lecture == obj['lecture']['series'])
            ) or (
                type == 'lecture'
                and (not staff or [p for p in obj['staff'] if p['id'] == staff])
                and (not semester or ('semester' in obj and obj['semester'] == semester))
                and (not series or 'series' in obj and obj['series'] == series)
                and (not studygroup or ('studygroup' in obj and obj['studygroup'] in wrap_list(studygroup)))
            ) or (
                type == 'post'
            ) or (
                type == 'service'
                and (not entrysubtype or (obj['entrysubtype'] in wrap_list(entrysubtype)))
            )
            ):
                if id(obj) not in captured:
                    ret.append(obj)
                    captured.add(id(obj))
        for x in ret:
            self.__reference(x)
        return self.sorted(ret)

    def sorted(self, elem, **kwargs):
        def sort_key(x):
            if type(x) is not dict:
                return x
            if self.isA(x, 'publication'):
                year =  int(x['bibtex'].get('year', '0'))
                return str(10000-year) + x.get('title', '') + x['id']
            if self.isA(x, 'news') or self.isA(x, 'post'):
                return (x['date'], x['title'])
            if self.isA(x, 'lecture'):
                return x['sortkey']
            if self.isA(x, 'evaluation'):
                return x['lecture']['sortkey'] + x.get('note', "")
            if self.isA(x, 'service'):
                if('year' in x):
                    return str(x['year'])
                else:
                    return x['title']
            if 'id' in x:
                return x['id']
            return str(x)
        return sorted(elem, key = sort_key)
