import pprint

def p_print(*args, stripped=True):
    """ Pretty print all python types.

    Customized pretty printer. Use for debugging purposes.
    Especially useful for the objects dict.

    Usage:
        from util import p_print
        p_print(foo)

    Arguments:
    *args -- Print this types

    Keyword arguments:
    stripped -- If True, strip out all occurences of 'page-body'
    """
    newargs = []
    if stripped:
        for arg in args:
            if isinstance(arg, dict) and 'page-body' in arg:
                tmp = arg.copy()
                tmp['page-body'] = '<stripped>'
                newargs.append(tmp)
            else:
                newargs.append(arg)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(*newargs)
