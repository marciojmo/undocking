import string

from ship_api import slug


def test_generate_slug_has_requested_length():
    assert len(slug.generate_slug(10)) == 10
    assert len(slug.generate_slug(20)) == 20


def test_generate_slug_uses_lowercase_alphanumerics():
    allowed = set(string.ascii_lowercase + string.digits)
    assert set(slug.generate_slug(50)) <= allowed


def test_generate_slug_is_random():
    assert slug.generate_slug() != slug.generate_slug()


def test_sanitize_slug_lowercases_and_replaces_spaces():
    assert slug.sanitize_slug("My First Post") == "my-first-post"


def test_sanitize_slug_collapses_repeated_separators():
    assert slug.sanitize_slug("a---b___c") == "a-b-c"


def test_sanitize_slug_strips_leading_and_trailing_hyphens():
    assert slug.sanitize_slug("  !hello!  ") == "hello"


def test_sanitize_slug_caps_length_at_64():
    assert len(slug.sanitize_slug("a" * 200)) == 64
