from app.services.google_chat import to_chat_markup


def test_bold_headings_and_links_use_chat_markup() -> None:
    text = "# Steps\n**Check** the __version__ at [PHP](https://php.net/x)."

    assert to_chat_markup(text) == "*Steps*\n*Check* the *version* at <https://php.net/x|PHP>."


def test_code_fence_loses_its_language_label_and_keeps_its_content() -> None:
    text = "Run:\n```bash\nphp -v\n# not a heading\n**kept**\n```\nDone **now**"

    assert to_chat_markup(text) == ("Run:\n```\nphp -v\n# not a heading\n**kept**\n```\nDone *now*")


def test_chat_markup_and_bullets_are_left_alone() -> None:
    text = "*bold* _it_ `code`\n- one\n* two\n1. three"

    assert to_chat_markup(text) == text


def test_plain_text_is_unchanged() -> None:
    assert to_chat_markup("Got it") == "Got it"
