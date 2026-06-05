"""Go handler for mkdocstrings."""

from mkdocstrings_handlers.go._internal.config import (
    GoConfig,
    GoInputConfig,
    GoInputOptions,
    GoOptions,
)
from mkdocstrings_handlers.go._internal.handler import (
    GoDoc,
    GoField,
    GoFunction,
    GoHandler,
    GoInterface,
    GoPackageDoc,
    GoParam,
    GoStruct,
    GoTypeAlias,
    GoValue,
    get_handler,
    merge_package_docs,
    parse_go_source,
)

__all__ = [
    "GoConfig",
    "GoDoc",
    "GoField",
    "GoFunction",
    "GoHandler",
    "GoInputConfig",
    "GoInputOptions",
    "GoInterface",
    "GoOptions",
    "GoPackageDoc",
    "GoParam",
    "GoStruct",
    "GoTypeAlias",
    "GoValue",
    "get_handler",
    "merge_package_docs",
    "parse_go_source",
]
