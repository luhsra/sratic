---
id: main
title: SRAtic - The static website generator for academic institutions
---
# {{ page.title }} #

## Design Principles ##

- Everything that is a page or that has an id field is an object!
- Every object that has a type is validated against the schema (data/schema.yml).
- All objects have a unique ID.
- Objects have fields.

SRAtic is a static website generator, that is developed to generate
websites that consist of many structured data objects, which are
displayed, filtered, listed, and cross-referenced. Its initial use is
targeted at academic institutions to provide a structured CMS system
that does not suck, but can reflect the several aspects of research
and teaching and the assiciated use cases.

SRAtic has two main components:

- Page content that is mainly written  in
  [Markdown](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet),
  but that contains also [jinja2 templates](http://jinja.pocoo.org/docs/2.9/).
- Structured data, which is attached to pages or free floating,
  expressed in [YAML](https://en.wikipedia.org/wiki/YAML). The data
  can be referenced from the jinja templates.


As an example, let's examine the source code of this page:

    {% raw %}---
    id: main
    title: SRAtic -The static website generator for academic institutions
    ---
    # {{ page.title }} #
    {% endraw%}

This page is saved, as `index.md` and has a YAML preface, which
defines data that is valid for the processing of this concrete
document. This page has the id `main` and defines a variable title. In
the body of the page, the title is referenced by `page.title` in the
jinja2 block. All data that is noted in the YAML preface, as well as
all variables from the diretory-wide `variables.yml` file are
available from the `page.` namespace.

However, this page and its data is also available from the object
namespace, where we man retrieve it by the `deref` function:

    {% raw %}{{ deref('main').title }}{% endraw %}

This expression is equivalent to the previous one, but can be used
from any other document. Please note, that the single quotes are
necessary for jinja2; double quotes will not work. Besides the YAML
preface, data can also be specified in in the `data/root.yml` file.

In the following, we will discuss a few very useful concepts that act
mainly on the object space.

## Special YAML constructors ##

When YAML data is read in by SRAtic, there are special operators to
make life and maintainability of websites easier.

- `!include <filename.yml>`\
   With the include statement, the data from
   another file can be included at exactly that position. The
   statement is then replaced with the actual data of the referenced
   yaml file.

- `!splice <filename.yml>` \
   This operation is very similar to the include statement, but it
   includes the referenced data into the parent of the `!splice`
   statement. It splices the data into the parent. For example, a
   !splice operation within a list does splice the referenced data,
   which must be also an list into the containing list. The mechanism also works for dictionaries.

        root.yml: [0, !splice "a.yml", 2, 3]
        a.yml: [2, 35]

        -> [0, 2, 35, 2, 3]

- `!bibtex <file.bib>` \
  Works like the !include statement, but reads in bibtex data. For a
  detailed information on !bibtex, see the corresponding section.

- `!path <filename>` \
  Generates a full path that starts with /. For example, if we use
  `!path foo` in `/Lehre/L_KHP`, then the constructor will expand to
  `/Lehre/L_KHP/foo`.

## Objects and schema checking ##

First of all, an object can live everywhere in the data structure that
is defined by the page preface, the directory-local `variables.yml`
file or the data directory (`data/root.yml`). Every dictionary (in
other languages it is often called hash or associative array) that has
an `id` field is an object. Therefore this snippet of yaml, which is a
list of dictionaries contains three objects `a`, `b`, and `c`:

    - id: a
    - id: b
    - id: c
      type foo

Furthermore, an object can have a type. Then type checking is employed
against that specific object. In our example, object `c` is of type
`foo`. All types are defined in `data/schema.yml`. If a type is not
known, the generator will abort its operation until someone fixes the
issue. The type checking is done on the field level. The general
format of the schema definition is:

    <TYPE>:
       <FIELD>:
          <RULE 1>:
          <RULE 2>
          ...

Possible rules are:

- `required`: The specific field must be present in the object.
- `recommended`: A warning is emitted, if the field is missing.
- `type`: The field must be of the given type. Currently the following
  types are available: int, bool, boolean, str, string, date, float, list, dict.
- `enum`: The field value must be any of the given values.

## Parent-child relations between pages ##

Objects can be assoicated in a parent-child relationship. This is
especially useful for hierarchical structures, like page objects that
should be structured in a tree. A parent-child relationship can either
be established, by directly defining an object at the parent, by
adding an reference, or by declaring the parent explicitly for an
object.

    - id: A
      children:
         - id: B
           foo: 123
         - D
    - id: C
      parent: A
    - id: D

In this example, the element A, will end up with three child objects
[`B`, `D`, `C`], in that order. Please be aware, that you should
always use `deref()` when iterating over childrend, and that the order
of children that are soley attached by `parent:` have a random order.

## Publication data and bibtex entries ##

As SRAtic is designed for the use in an academic environment, reading
and displaying publication data is of uttermost importance. Therefore,
bibtex entries can automatically be read in and transformed to proper
objects. Their object id is derived from the bibtex key and prepended
with `bib:`.

Bibtex entries are automatically attached to objects that have exactly
the bibtex key as an object identifier. If no such publication object
exists, which will be a publication page most of the time, a surrogate
object is defined and included into the object space. In the
associated publication object the bibtex entry is available at
`.bibtex`. Starting from the publication object a few fields are
automatically filled by SRAtic:

- `pub.title`: Title from the bibtex entry
- `pub.projects`: Equal to `pub.bibtex.projects`
- `pub.bibtex`: The bibtex object
- `pub.bibtex.projects`: Is automatically splitted and stripped at commas
- `pub.bibtex.bibtex`: The string representation of the raw bibtex entry

For the bibtex entries, a few fields are used to show the publication:

- doi: Used for a [DOI] link
- pdf: Used for a [PDF] link
- x-projects: A comma separated list of project ids
- x-rawdata: Used for a [Raw Data] link
- x-slides: Used for a [Slides] link

## SRAtic Dependency tracking ##

In order to speed up the generation of larger websites. SRAtic tries
to track dependencies between pages. A page is only regenerated, if
any of its dependencies has a newer modification date that the result
of the generation process (a timestamp-based dependency tracking, like
it is also done by make). However, we employ a few heuristics to catch
most dependencies without annotating them:

- Every parent object depends on all its child objects
- Every page depends on `data/root.yml`
- Dependencies resulting from `!include`, `!splice`, and other
  constructors are properly tracked.
- Pages can explicilty use the `depends: LIST` key in their YAML
  preface to annotate another dependency.

## Reference and Cheatsheet ##

### Text emitting macros ###

- `nav.link(<OBJECT or ID>)`\
  Generates a link to the given object, which can either be supplied
  by its id or directly. A link c

  Since linking to an object is such a common operation, we introduced
  the non-markdown syntax of `[[<OBJECT-ID>]]` and
  `[[<OBJECT-ID>][<TITLE>]]` as a shortcut for `nav.link()`.

- `show.show(<OBJECT or ID>)`\
   Show a short summary of the given object according to its type.

- `show.list(type, **filters, show_list=False)`\
  Iterate over all known objects of the given type and apply some
  filtering on the objects. If an object has `show.list` set to false,
  the object is only selected, if the argument
  `show_list=True` is given.
  For different types, different filters are available:
    - thesis:
        - status:     thesis is in any of the given stati
        - supervisor: the given person is one of the supervisors
        - project:    thesis is linked to the project
    - project:
        - status:      project has the given status
    - publication:
        - project:     publication is linked to the project

### Helper Functions ###

- `deref(<OBJECT or ID>)`\
  Dereferences an id, if it should be necessary. If an object is given,
  it is immediatly returned. If the ID is not found, the dereference
  operator fails.

## SRAtic Package requirements ##

### Debian
- python3
- python3-bibtexparser
- python3-yaml
- python3-jinja2
- pandoc

All of these are installed on the lab machines.

### Installation on MacOS (with MacPorts)
- install **python3** and related packages:
  `sudo port install python36 py36-jinja2 py36-yaml py36-pip`
- set **python36** as the default **python3**:
  `sudo port select --set python3 python36`
- the **bibtexparser** is not included in MacPorts, so we need to install via pip:
  `sudo pip-3.6 install bibtexparser`
- **pandoc** is available in MacPorts, but the version 1.12 is too old. So we install it directly from http://pandoc.org/installing.html
