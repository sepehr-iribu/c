"""This module implements a handler for the Go language."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from os import sep as path_sep
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from mkdocs.exceptions import PluginError
from mkdocstrings import BaseHandler, CollectionError, CollectorItem

from mkdocstrings_handlers.go._internal.config import GoOptions

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

    from mkdocs.config.defaults import MkDocsConfig


_COMMENT_LINE = re.compile(r"^\s*//\s?(.*)$")
_PACKAGE = re.compile(r"^\s*package\s+([A-Za-z_]\w*)\s*$")
_FUNC = re.compile(
    r"^func\s*(?:\((?P<receiver>[^)]+)\)\s*)?(?P<name>[A-Za-z_]\w*)(?P<tparams>\[[^]]+\])?\s*\((?P<params>[^)]*)\)\s*(?P<results>.*)$",
)
_TYPE = re.compile(r"^type\s+(?P<name>[A-Za-z_]\w*)(?P<tparams>\[[^]]+\])?\s+(?P<body>.+)$", re.DOTALL)
_DECL = re.compile(r"^(?P<kind>const|var)\s+(?P<body>.+)$")


@dataclass
class GoDoc:
    """A parsed Go doc comment."""

    desc: str


@dataclass
class GoParam:
    """A function parameter or result item."""

    name: str
    tp: str


@dataclass
class GoField:
    """A struct field."""

    name: str
    tp: str
    embedded: bool = False
    doc: GoDoc | None = None


@dataclass
class GoFunction:
    """A function or method."""

    name: str
    params: list[GoParam]
    results: list[GoParam]
    receiver: str | None = None
    type_params: str = ""
    doc: GoDoc | None = None


@dataclass
class GoStruct:
    """A struct type."""

    name: str
    fields: list[GoField]
    type_params: str = ""
    doc: GoDoc | None = None


@dataclass
class GoInterface:
    """An interface type."""

    name: str
    methods: list[str]
    embeds: list[str]
    type_params: str = ""
    doc: GoDoc | None = None


@dataclass
class GoValue:
    """A const/var declaration."""

    name: str
    tp: str | None
    value: str | None
    kind: str
    doc: GoDoc | None = None


@dataclass
class GoTypeAlias:
    """A custom type alias/definition."""

    name: str
    target: str
    type_params: str = ""
    doc: GoDoc | None = None


@dataclass
class GoPackageDoc:
    """Top-level rendered package data."""

    package: str
    path: str
    files: list[str] = field(default_factory=list)
    functions: list[GoFunction] = field(default_factory=list)
    methods: list[GoFunction] = field(default_factory=list)
    structs: list[GoStruct] = field(default_factory=list)
    interfaces: list[GoInterface] = field(default_factory=list)
    consts: list[GoValue] = field(default_factory=list)
    vars: list[GoValue] = field(default_factory=list)
    types: list[GoTypeAlias] = field(default_factory=list)


def _is_exported(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _clean_doc(lines: list[str]) -> GoDoc | None:
    text = "\n".join(line.rstrip() for line in lines if line.strip()).strip()
    return GoDoc(text) if text else None


def _split_decl_lines(source: str) -> list[tuple[str, GoDoc | None]]:
    declarations: list[tuple[str, GoDoc | None]] = []
    doc_lines: list[str] = []
    block_buffer: list[str] = []
    block_depth = 0

    for raw_line in source.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("/*"):
            doc_lines.append(stripped.removeprefix("/*").removesuffix("*/").strip(" *"))
            continue

        comment_match = _COMMENT_LINE.match(line)
        if comment_match:
            doc_lines.append(comment_match.group(1))
            continue

        if not stripped:
            if block_depth == 0:
                doc_lines = []
            continue

        if block_depth > 0:
            block_buffer.append(line)
            block_depth += line.count("{") - line.count("}")
            if block_depth <= 0:
                declarations.append(("\n".join(block_buffer).strip(), _clean_doc(doc_lines)))
                block_buffer = []
                doc_lines = []
                block_depth = 0
            continue

        if stripped.startswith(("func ", "type ")) and "{" in stripped and not stripped.endswith("}"):
            block_buffer = [line]
            block_depth = line.count("{") - line.count("}")
            continue

        declarations.append((stripped, _clean_doc(doc_lines)))
        doc_lines = []

    return declarations


def _parse_param_group(group: str) -> list[GoParam]:
    if not (group := group.strip()):
        return []

    if group.startswith("(") and group.endswith(")"):
        group = group[1:-1]

    results: list[GoParam] = []
    for item in [part.strip() for part in group.split(",") if part.strip()]:
        parts = item.split()
        if len(parts) == 1:
            results.append(GoParam("", parts[0]))
        else:
            results.append(GoParam(parts[0], " ".join(parts[1:])))
    return results


def _parse_func(signature: str, doc: GoDoc | None) -> GoFunction | None:
    signature = signature.split("{", 1)[0].strip()
    match = _FUNC.match(signature)
    if not match:
        return None

    results = _parse_param_group(match.group("results") or "")
    return GoFunction(
        name=match.group("name"),
        receiver=(match.group("receiver") or "").strip() or None,
        type_params=(match.group("tparams") or "").strip(),
        params=_parse_param_group(match.group("params") or ""),
        results=results,
        doc=doc,
    )


def _parse_struct_fields(body: str) -> list[GoField]:
    fields: list[GoField] = []
    inside = body.split("{", 1)[1].rsplit("}", 1)[0]
    for line in inside.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        parts = stripped.split()
        if len(parts) == 1:
            fields.append(GoField(name=parts[0], tp=parts[0], embedded=True))
        else:
            fields.append(GoField(name=parts[0], tp=" ".join(parts[1:])))
    return fields


def _parse_interface_items(body: str) -> tuple[list[str], list[str]]:
    methods: list[str] = []
    embeds: list[str] = []
    inside = body.split("{", 1)[1].rsplit("}", 1)[0]
    for line in inside.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if "(" in stripped:
            methods.append(stripped)
        else:
            embeds.append(stripped)
    return methods, embeds


def _parse_type(signature: str, doc: GoDoc | None) -> GoStruct | GoInterface | GoTypeAlias | None:
    match = _TYPE.match(signature.strip())
    if not match:
        return None

    name = match.group("name")
    tparams = (match.group("tparams") or "").strip()
    body = match.group("body").strip()

    if body.startswith("struct") and "{" in body:
        return GoStruct(name=name, fields=_parse_struct_fields(body), type_params=tparams, doc=doc)
    if body.startswith("interface") and "{" in body:
        methods, embeds = _parse_interface_items(body)
        return GoInterface(name=name, methods=methods, embeds=embeds, type_params=tparams, doc=doc)
    return GoTypeAlias(name=name, target=body, type_params=tparams, doc=doc)


def _parse_value_item(kind: str, item: str, doc: GoDoc | None) -> GoValue | None:
    if not item:
        return None

    head, sep, value = item.partition("=")
    lhs = head.strip()
    lhs_parts = lhs.split()
    if not lhs_parts:
        return None

    name = lhs_parts[0]
    tp = " ".join(lhs_parts[1:]) or None
    rhs = value.strip() if sep else None
    return GoValue(name=name, tp=tp, value=rhs, kind=kind, doc=doc)


def _parse_value(signature: str, doc: GoDoc | None) -> list[GoValue]:
    match = _DECL.match(signature.strip())
    if not match:
        return []

    kind = match.group("kind")
    body = match.group("body").strip()
    if body.startswith("(") and body.endswith(")"):
        entries = [line.strip() for line in body[1:-1].splitlines() if line.strip()]
        return [value for line in entries if (value := _parse_value_item(kind, line, doc))]

    value = _parse_value_item(kind, body, doc)
    return [value] if value else []


def parse_go_source(source: str, package_path: str, filename: str, *, include_private: bool = False) -> GoPackageDoc:
    """Parse a Go source file into renderable data."""
    package = "main"
    for line in source.splitlines():
        if match := _PACKAGE.match(line):
            package = match.group(1)
            break

    parsed = GoPackageDoc(package=package, path=package_path, files=[filename])

    for declaration, doc in _split_decl_lines(source):
        if declaration.startswith("func "):
            if not (func := _parse_func(declaration, doc)):
                continue
            if not include_private and not _is_exported(func.name):
                continue
            if func.receiver:
                parsed.methods.append(func)
            else:
                parsed.functions.append(func)
            continue

        if declaration.startswith("type "):
            parsed_type = _parse_type(declaration, doc)
            if not parsed_type:
                continue
            if not include_private and not _is_exported(parsed_type.name):
                continue
            if isinstance(parsed_type, GoStruct):
                parsed.structs.append(parsed_type)
            elif isinstance(parsed_type, GoInterface):
                parsed.interfaces.append(parsed_type)
            else:
                parsed.types.append(parsed_type)
            continue

        if declaration.startswith(("const ", "var ")):
            for value in _parse_value(declaration, doc):
                if include_private or _is_exported(value.name):
                    if value.kind == "const":
                        parsed.consts.append(value)
                    else:
                        parsed.vars.append(value)

    return parsed


def merge_package_docs(parts: list[GoPackageDoc], path: str) -> GoPackageDoc:
    """Merge docs extracted from multiple files."""
    if not parts:
        return GoPackageDoc(package="main", path=path)

    merged = GoPackageDoc(package=parts[0].package, path=path)
    for part in parts:
        merged.files.extend(part.files)
        merged.functions.extend(part.functions)
        merged.methods.extend(part.methods)
        merged.structs.extend(part.structs)
        merged.interfaces.extend(part.interfaces)
        merged.consts.extend(part.consts)
        merged.vars.extend(part.vars)
        merged.types.extend(part.types)
    return merged


class GoHandler(BaseHandler):
    """The Go handler class."""

    name: ClassVar[str] = "go"
    domain: ClassVar[str] = "go"
    enable_inventory: ClassVar[bool] = False
    fallback_theme: ClassVar[str] = "material"

    def __init__(self, config: Mapping[str, Any], base_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.base_dir = base_dir
        self.global_options = config.get("options", {})

    def get_options(self, local_options: Mapping[str, Any]) -> GoOptions:
        extra = {**self.global_options.get("extra", {}), **local_options.get("extra", {})}
        options = {**self.global_options, **local_options, "extra": extra}
        try:
            return GoOptions.from_data(**options)
        except Exception as error:
            raise PluginError(f"Invalid options: {error}") from error

    def _candidate_paths(self, identifier: str) -> list[Path]:
        candidate = Path(identifier)
        if candidate.is_absolute():
            return [candidate]

        direct = self.base_dir / identifier
        module_style = self.base_dir / identifier.replace("/", path_sep)
        return [direct, module_style]

    def _go_files(self, path: Path, *, recursive: bool, include_tests: bool) -> list[Path]:
        globber = path.rglob if recursive else path.glob
        files = sorted(globber("*.go"))
        if include_tests:
            return [file for file in files if file.is_file()]
        return [file for file in files if file.is_file() and not file.name.endswith("_test.go")]

    def collect(self, identifier: str, options: GoOptions) -> CollectorItem:
        if not options:
            raise CollectionError("Not loading additional files during fallback")

        chosen_path = None
        for candidate in self._candidate_paths(identifier):
            if candidate.exists():
                chosen_path = candidate
                break

        if chosen_path is None:
            raise CollectionError(f"Could not resolve Go identifier: {identifier}")

        if chosen_path.is_file():
            if chosen_path.suffix != ".go":
                raise CollectionError(f"Not a Go source file: {chosen_path}")
            source = chosen_path.read_text(encoding="utf-8")
            return parse_go_source(
                source,
                package_path=str(chosen_path.parent),
                filename=chosen_path.name,
                include_private=options.include_private,
            )

        files = self._go_files(chosen_path, recursive=options.recursive, include_tests=options.include_tests)
        if not files:
            raise CollectionError(f"No Go files found under: {chosen_path}")

        docs = [
            parse_go_source(
                file.read_text(encoding="utf-8"),
                package_path=str(chosen_path),
                filename=file.name,
                include_private=options.include_private,
            )
            for file in files
        ]
        return merge_package_docs(docs, str(chosen_path))

    def render(self, data: GoPackageDoc, options: GoOptions, *, locale: str | None = None) -> str:  # noqa: ARG002
        heading_level = options.heading_level
        template = self.env.get_template("header.html.jinja")
        return template.render(config=options, header=data, heading_level=heading_level, root=True)

    def update_env(self, config: dict) -> None:  # noqa: ARG002
        self.env.trim_blocks = True
        self.env.lstrip_blocks = True
        self.env.keep_trailing_newline = False


def get_handler(
    handler_config: MutableMapping[str, Any],
    tool_config: MkDocsConfig,
    **kwargs: Any,
) -> GoHandler:
    """Return an instance of `GoHandler`."""
    base_dir = Path(tool_config.config_file_path or "./mkdocs.yml").parent
    return GoHandler(config=handler_config, base_dir=base_dir, **kwargs)
