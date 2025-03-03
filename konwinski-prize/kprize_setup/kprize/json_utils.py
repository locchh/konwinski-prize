import json


def jsons(obj, default: any = None):
    """
    Return pretty JSON string with indent 2
    """
    return json.dumps(obj, default=default, indent=2)


