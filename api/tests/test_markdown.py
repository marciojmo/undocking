from ship_api import markdown


def test_wrap_html_produces_full_document():
    html = markdown.wrap_html("<p>hi</p>")
    assert html.startswith("<!DOCTYPE html>")
    assert "<p>hi</p>" in html
    assert "</html>" in html.strip()


def test_render_markdown_converts_headings():
    html = markdown.render_markdown("# Title")
    assert "<h1>Title</h1>" in html


def test_render_markdown_wraps_output():
    html = markdown.render_markdown("hello")
    assert html.startswith("<!DOCTYPE html>")


def test_render_markdown_strips_script_tags():
    html = markdown.render_markdown("Hello <script>alert('xss')</script>")
    assert "<script>" not in html
    assert "alert" not in html


def test_render_markdown_keeps_extra_allowed_tags():
    html = markdown.render_markdown("<details><summary>More</summary>body</details>")
    assert "<details>" in html
    assert "<summary>" in html
