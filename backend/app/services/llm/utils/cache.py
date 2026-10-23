"""An LRU cache for async methods.

`functools.lru_cache` does not work on coroutines, and the arguments here are not hashable --
they are Pydantic models, dataclasses, dicts of lists. `freeze_for_cache` turns any of that into
something hashable, deterministically, so equal arguments produce equal keys.

The settings object is part of every key by identity. Two gateways configured differently must not
read each other's answers, and comparing settings by value would be both slower and wrong.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, is_dataclass
from functools import wraps
from typing import Any

from pydantic import BaseModel


def freeze_for_cache(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseModel):
        return freeze_for_cache(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return freeze_for_cache(asdict(value))
    if isinstance(value, dict):
        return tuple(sorted((str(key), freeze_for_cache(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_for_cache(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((freeze_for_cache(item) for item in value), key=repr))
    return repr(value)


def async_lru_cache(maxsize: int = 128):
    def decorator(func):
        cache: OrderedDict[Any, Any] = OrderedDict()

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            key = (id(getattr(self, "settings", None)), freeze_for_cache(args), freeze_for_cache(kwargs))
            if key in cache:
                cache.move_to_end(key)
                return cache[key]

            result = await func(self, *args, **kwargs)
            cache[key] = result
            cache.move_to_end(key)
            while len(cache) > maxsize:
                cache.popitem(last=False)
            return result

        return wrapper

    return decorator
