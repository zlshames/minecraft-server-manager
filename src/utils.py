def get_with_default(obj, key, default=None):
    return obj.get(key, default) or default