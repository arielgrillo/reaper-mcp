# Backlog viewer

From the repository root, start a local static server:

```text
uv run python -m http.server 8000 --directory tasks
```

Then open `http://127.0.0.1:8000/` in a browser.

The viewer reads `backlog.json` directly, so backlog updates require no changes to the UI files.
