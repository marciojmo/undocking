import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt()

_EXTRA_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "img",
    "video",
    "source",
    "details",
    "summary",
    "mark",
    "del",
    "ins",
    "kbd",
    "sup",
    "sub",
}


def render_markdown(content: str) -> str:
    """Renders Markdown to a sanitized, fully wrapped HTML document."""
    raw = _md.render(content)
    safe = nh3.clean(raw, tags=nh3.ALLOWED_TAGS | _EXTRA_TAGS)
    return wrap_html(safe)


def wrap_html(body: str) -> str:
    """Wraps an HTML body fragment in a styled, standalone HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ margin: 0 auto; max-width: 800px; padding: 2rem 1.5rem; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 1rem; line-height: 1.7; color: #1a1a1a; background: #fff; }}
  h1, h2, h3, h4, h5, h6 {{ line-height: 1.3; margin: 1.5em 0 0.5em; }}
  h1 {{ font-size: 2rem; }} h2 {{ font-size: 1.5rem; }}
  a {{ color: #0070f3; }}
  pre {{ background: #f4f4f5; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
  code {{ font-family: "Fira Code", Consolas, monospace; font-size: 0.9em; }}
  pre code {{ background: none; }}
  code:not(pre code) {{ background: #f4f4f5; padding: 0.1em 0.3em; border-radius: 3px; }}
  blockquote {{ border-left: 4px solid #e5e7eb; margin: 0; padding-left: 1rem; color: #6b7280; }}
  img {{ max-width: 100%; height: auto; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; }}
  th {{ background: #f9fafb; font-weight: 600; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
