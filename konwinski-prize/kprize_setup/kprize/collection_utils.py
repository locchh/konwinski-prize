def get_index_by_field(lst: list[dict], field, value):
    for index, item in enumerate(lst):
        if item[field] == value:
            return index
    return -1


def get_key_values(lst: list[dict], field):
    return list(map(lambda x: x[field], lst))


def get_item_by_field(l: list[dict], field: str, value: any):
    return next((p for p in list(l) if p[field] == value), None)


def get_index_by_starts_with(list_of_strs: list[str], value):
    for index, s in enumerate(list_of_strs):
        if s.startswith(value):
            return index
    return -1


def filter_by_key(lst: list[dict], key: str, values: list[any]):
    filtered = []
    grouped = group_by_key(lst, key)
    for v in values:
        filtered = filtered + grouped.get(v, [])
    return filtered


def group_by_key(lst: list[dict], key: str):
    grouped = {}
    for i in lst:
        value = i[key]
        if value not in grouped:
            grouped[value] = [i]
        else:
            grouped[value].append(i)
    return grouped


def print_list_with_indexes(lst: list):
    for idx, item in enumerate(lst):
        print(f"[{idx}] = {item}")


def get_index_or_default(lst: list, index: int, default):
    return lst[index] if index < len(lst) else default
