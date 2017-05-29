SRAtic -The static website generator for academic institutions
--------------------------------------------------------------

Principles:

- Everything that is a page or that has an id field is an object!
- Every object that has a type, is validated against the schema (data/schema.yml).
- objects have fields, and their ID is unique.

## Useful macros and operators ##

### Text emitting macros ###

- `nav.link(<OBJECT or ID>)`

  Generates a link to the given object, which can either be supplied
  by its id or directly.

- `show.show(<OBJECT or ID>)`

  Show a short summary of the given object according to its type.

- `show.list(type, **filters)`

  Iterate over all known objects of the given type and apply some
  filtering on the objects. For different types, different filters are
  available:
  - thesis:
     - status:     thesis is in any of the given stati
     - supervisor: the given person is one of the supervisors
     - project:    thesis is linked to the project
  - project:
    - status:      project has the given status
  - publication:
    - project:     publication is linked to the project

### Helper Functions ###

- deref(<OBJECT or ID>)

  Dereferences an id, if it should be necessary. If an object is
  given, it is immediatly returned. If the ID is not found, the
  dereference operator fails.
