import logging
import datetime


def check_schema(schema_document, obj, objects):
    """Validates a object  against the schema definition"""
    Type = obj.get('type')
    # If it has no type, we just can yes
    if not Type:
        return True

    # Generate a combined schema
    schema = {}
    for x in Type:
        schema.update(schema_document.data[x])

    for field,rules in schema.items():
        if rules.get('required'):
            assert field in obj,\
                "Required field '%s' is missing: %s" %(field, obj)

        if rules.get('recommended') and not field in obj:
            logging.warning(
                "Recommended field '%s' is missing: %s",
                field, obj['id'])
        if field not in obj:
            continue
        if 'type' in rules:
            ok, value = type_check_and_resolve(rules['type'],
                                               obj[field],
                                               objects)
            assert ok, \
                "Field '%s' has wrong type: %s != %s" %(field, rules['type'],
                                                        repr(obj[field]))
            if rules.get('deref'):
                obj[field] = value

        if rules.get('enum'):
            assert obj[field] in rules['enum'],\
                "Field '%s' has invalid value: %s not in  %s" %(field, obj[field],
                                                                rules['enum'])

    if schema:
        for field in obj.keys() - schema.keys():
            logging.info("Field not in schema: %s/%s", obj['id'], field)

def type_check_and_resolve(pattern, value, objects):
    if type(pattern) is str:
        # Base types
        base_types = {'int': int,
                      'bool': bool,
                      'boolean': bool,
                      'str': str,
                      'string':str,
                      'date': datetime.date,
                      'float': float,
                      'url': str,
                      'list': list,
                      'dict': dict}
        if pattern in base_types:
            return (type(value) is base_types[pattern],
                    value)
        elif pattern.startswith('object.'):
            T = pattern[len('object.'):]
            deref = objects.deref(value, fail=False)
            if not deref:
                logging.error("Dangling Reference! {}".format(value))
                return (False, value)
            return (T in deref['type'], deref)
        else:
            raise RuntimeError("Invalid schema type pattern: " + pattern)
    if type(pattern) is list:
        assert len(pattern) == 1, 'Wrong type definition'
        if type(value) not in (list,tuple):
            return (False, value)
        ret_list = [type_check_and_resolve(pattern[0], x, objects)
                    for x in value]
        return (all([x[0] for x in ret_list]),
                [x[1] for x in ret_list])
    return (False, value)
