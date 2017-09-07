from .schema import check_schema
import os.path as osp

def wrap_list(lst):
    if not lst:
        return []
    if type(lst) != list:
        return [lst]
    return lst

class ObjectStore:
    def __init__(self):
        self.objects = {}
        self.page_objects = {}

    def crawl_pages(self, schema, data_dir, pages):
        # The dict that maps every object id to its object
        # ID -> object
        objects = self.objects

        # ID -> YAMLFragment
        page_objects = {}

        # Step 1: Every page object should have an ID. If it does not
        # have an ID, we assign the local part of the page as an id. E.g.
        # `/index.html' for the root page
        for page in pages:
            (base, ext) = osp.splitext(page.path)
            page.data['href'] = base[1:] + ".html"
            if not "id" in page.data:
                page.data['id'] = page.data['href']

            # Step 1.1: include all objects in this page to the object
            # index.
            for obj in page.objects():
                objects[obj['id']] = obj
            # Step 1.2: build an index of all page yaml fragments
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

        # Step 2: Generate an Index for all objects that are defined in the data directory
        for obj in data_dir.objects():
            assert obj['id'] not in objects, "Duplicate Object ID (%s)" %(obj['id'])
            objects[obj['id']] = obj

        # Step 3: Generate publication object, if they are not present.
        for obj in list(objects.values()):
            if self.isA(obj, 'bibtex'):
                if obj['ID'] in objects:
                    page = objects[obj['ID']]
                else:
                    # Generate a surrogate publication object
                    page = {'id': obj['ID'], 'type': 'publication' }
                    obj['__surrogate_object'] = page
                    objects[page['id']] = page

                # Update some fields from the bibtex entry
                page['bibtex'] = obj
                if not 'title' in page:
                    page['title'] = obj['title']
                # Extract list of projects from bibtex file
                page['projects'] = list(filter(None, [x.strip() for x in obj.get('x-projects','').split(",")]))

        # Step 5: Assemble the sitemap and the parent->child relation
        for obj in objects.values():
            if 'parent' in obj:
                p = obj['id']
                pp = obj['parent']
                assert obj['parent'] in objects, \
                    "Parent %s is unknown (fn=%s)"%(pp, page.path)
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


            # Wrap the dependencies, when we're at it
            # Then this works also
            #   depends: main
            if 'depends' in obj:

                obj['depends'] = wrap_list(obj['depends'])


        # Step 6: Validate the schema for all objects, we are aware of.
        for obj in objects.values():
            # Do a schema validation for the page data
            check_schema(schema, obj)


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

        # Step 8: Generate alias IDs for some objects
        for obj in list(objects.values()):
            aliases = []
            if self.isA(obj, 'person'):
                aliases.append(obj['name'])
            for id in aliases:
                if id in objects:
                    assert obj == objects[id],\
                        "Duplicate object ID: %s" %(id)
                else:
                    objects[id] = obj

        self.objects = objects

        # Step 9: For each page, find the page that holds its menu and
        # add an according dependency
        for page in pages:
            p = page
            while p:
                if self.has_menu_children(p.data):
                    page.sources.add(p.path)
                    break
                # Search in parent
                if 'parent' not in p.data:
                    break
                else:
                    p = page_objects[p.data['parent']]

    def has_menu_children(self, elem):
        entries = self.deref(elem).get('menu') or self.deref(elem).get('children', [])
        for p in entries:
            p = self.deref(p)
            if p.get('menu.list', True):
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


    def deref(self, elem):
        """Dereferences a object, if it should be necessary"""
        if type(elem) is dict:
            return elem
        else:
            return self.objects[elem]

    def isA(self, obj, Type):
        assert type(Type) is str
        if obj.get('type', None) == Type:
            return True
        if type(obj.get('type')) is list:
            return Type in obj['type']
        return False


    def object_list(self, type,
                      status=None,
                      supervisor=None,
                      project=None,
                      author=None,
                      own=None,
                      bibtype=None,
                      show_list=False):
        ret = []
        for obj in self.objects.values():
            if self.isA(obj, type) \
            and (obj.get('show.list', 'true') or show_list) \
            and ((
                type == 'thesis'
                and (not status or obj['thesis-status'] in status)
                and (not supervisor or supervisor in obj['thesis-supervisor'])
                and (not project or project in obj['projects'])
            ) or (
                type == 'project'
                and (not status or obj['project-status'] in status)
            ) or (
                type == 'publication'
                and (not project or project in obj['projects'])
                and (own == None or own == obj['bibtex'].get('x-own', False))
                and (not bibtype or obj['bibtex']['ENTRYTYPE'].lower() in wrap_list(bibtype))
                and (not author or (author in (obj['bibtex'].get('authors',[]) \
                                            + obj['bibtex'].get('editors',[]))))
            )):
                ret.append(obj)
        return self.sorted(ret)

    def sorted(self, elem, **kwargs):
        def sort_key(x):
            if self.isA(x, 'publication'):
                year =  int(x['bibtex'].get('year', '0'))
                return str(10000-year) + x.get('title', '') + x['id']
            if 'id' in x:
                return x['id']
            return str(x)
        return sorted(elem, key = sort_key)
