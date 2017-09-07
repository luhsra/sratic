import logging
import datetime


def check_schema(schema_document, obj):
    """Validates a object  against the schema definition"""
    Type = obj.get('type')
    # If it has no type, we just can yes
    if not Type:
        return True

    # Generate a combined schema
    if type(Type) is list:
        schema = {}
        for x in Type:
            schema.update(schema_document.data[x])
    else:
        schema = schema_document.data[Type]
    return __check_schema(schema, obj)

def __check_schema(schema, obj):
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
        if rules.get('type'):
            t = {'int': int,
                 'bool': bool,
                 'boolean': bool,
                 'str': str,
                 'string':str,
                 'date': datetime.date,
                 'float': float,
                 'url': str,
                 'list': list,
                 'dict': dict}[rules.get('type')]
            assert type(obj[field]) is t,\
                "Field '%s' has wrong type: %s != %s" %(field, t, type(obj[field]))

        if rules.get('enum'):
            assert obj[field] in rules['enum'],\
                "Field '%s' has invalid value: %s not in  %s" %(field, obj[field],
                                                                rules['enum'])

    if schema:
        for field in obj.keys() - schema.keys():
            if field == "baseurl":
                continue
            logging.info("Field not in schema: %s/%s", obj['id'], field)
