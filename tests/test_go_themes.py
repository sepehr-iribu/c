"""Theme rendering tests for the Go handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from markdown import Markdown
    from mkdocstrings import MkdocstringsPlugin


@pytest.mark.parametrize(
    "plugin",
    [
        {"theme": "mkdocs", "plugins": [{"mkdocstrings": {"default_handler": "go"}}]},
        {"theme": "readthedocs", "plugins": [{"mkdocstrings": {"default_handler": "go"}}]},
        {"theme": {"name": "material"}, "plugins": [{"mkdocstrings": {"default_handler": "go"}}]},
    ],
    indirect=["plugin"],
)
def test_render_themes_templates_go(plugin: MkdocstringsPlugin, ext_markdown: Markdown) -> None:
    handler = plugin.handlers.get_handler("go")
    handler._update_env(ext_markdown, config=plugin.handlers._tool_config)
    options = handler.get_options({})
    data = handler.collect("docs/snippets/hello.go", options)
    handler.render(data, options)
