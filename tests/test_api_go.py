"""Tests for Go public API exposition."""

from __future__ import annotations

from collections import defaultdict

import griffe

from mkdocstrings_handlers import go


def _yield_public_objects(obj: griffe.Module | griffe.Class):
    for member in obj.members.values():
        try:
            if member.is_module:
                if member.is_alias or not member.is_public:
                    continue
                yield from _yield_public_objects(member)  # type: ignore[arg-type]
            elif member.is_public:
                yield member
            else:
                continue
        except (griffe.AliasResolutionError, griffe.CyclicAliasError):
            continue


def test_exposed_objects() -> None:
    loader = griffe.GriffeLoader()
    loader.load("mkdocstrings_handlers.go")
    loader.resolve_aliases()
    internal_api = loader.modules_collection["mkdocstrings_handlers.go._internal"]

    modulelevel_internal_objects = list(_yield_public_objects(internal_api))
    not_exposed = [obj.path for obj in modulelevel_internal_objects if obj.name not in go.__all__ or not hasattr(go, obj.name)]
    assert not not_exposed, "Objects not exposed:\n" + "\n".join(sorted(not_exposed))


def test_unique_names() -> None:
    loader = griffe.GriffeLoader()
    loader.load("mkdocstrings_handlers.go")
    loader.resolve_aliases()
    internal_api = loader.modules_collection["mkdocstrings_handlers.go._internal"]

    names_to_paths = defaultdict(list)
    for obj in _yield_public_objects(internal_api):
        names_to_paths[obj.name].append(obj.path)
    non_unique = [paths for paths in names_to_paths.values() if len(paths) > 1]
    assert not non_unique, "Non-unique names:\n" + "\n".join(str(paths) for paths in non_unique)
