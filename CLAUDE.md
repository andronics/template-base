# CLAUDE.md

@AGENTS.md

When you change a template file, render it with a stack overlay and read the *output*:

```sh
uv run pytest tests/test_base.py -k checks_pass      # base + the stub stack overlay
```
