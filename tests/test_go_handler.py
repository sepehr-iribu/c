"""Tests for the Go handler parser and collector."""

from __future__ import annotations

from pathlib import Path

import pytest

from mkdocstrings_handlers.go import GoPackageDoc, parse_go_source


def test_parse_go_source_extracts_symbols() -> None:
    source = '''
package hello

// Version is exported.
const Version = "1.0.0"

// Counter stores state.
var Counter int

// Person is a sample struct.
type Person struct {
    Name string
    Age int
}

// Reader wraps reading behavior.
type Reader interface {
    Read(p []byte) (n int, err error)
}

// NewPerson creates a person.
func NewPerson(name string, age int) Person {
    return Person{Name: name, Age: age}
}

// Title returns a label.
func (p *Person) Title(prefix string) string {
    return prefix + p.Name
}
'''
    parsed = parse_go_source(source, package_path=".", filename="hello.go")

    assert parsed.package == "hello"
    assert [item.name for item in parsed.consts] == ["Version"]
    assert [item.name for item in parsed.vars] == ["Counter"]
    assert [item.name for item in parsed.structs] == ["Person"]
    assert [item.name for item in parsed.interfaces] == ["Reader"]
    assert [item.name for item in parsed.functions] == ["NewPerson"]
    assert [item.name for item in parsed.methods] == ["Title"]


@pytest.mark.parametrize(
    "plugin",
    [{"theme": {"name": "material"}, "plugins": [{"mkdocstrings": {"default_handler": "go"}}]}],
    indirect=["plugin"],
)
def test_collect_and_render_go(plugin, ext_markdown) -> None:  # type: ignore[no-untyped-def]
    handler = plugin.handlers.get_handler("go")
    handler._update_env(ext_markdown, config=plugin.handlers._tool_config)
    options = handler.get_options({})
    data = handler.collect(str(Path("docs/snippets/hello.go")), options)

    assert isinstance(data, GoPackageDoc)
    rendered = handler.render(data, options)
    assert "Greeter" in rendered
    assert "NewGreeter" in rendered
