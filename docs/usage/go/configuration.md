# Go configuration

## Global/local options

You can configure Go handler options globally in `mkdocs.yml`:

```yaml
plugins:
- mkdocstrings:
    handlers:
      go:
        options:
          recursive: true
          include_private: false
          include_tests: false
          show_symbol_type_heading: true
          show_symbol_type_toc: true
```

You can override these options locally per identifier block.
