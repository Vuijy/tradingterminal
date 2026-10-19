from app.services.filing_text import find_sections, html_to_text, split_sentences

HTML = """
<html><head><title>x</title><style>p{}</style></head><body>
<div style="display:none"><ix:header><div>hidden xbrl header</div></ix:header></div>
<div style="display: none">also hidden<div>nested hidden</div></div>
<p>Visible paragraph one.</p>
<table><tr><td>Cell A</td><td>Cell B</td></tr></table>
<p>We purchase memory from SK Hynix Inc., Micron Technology, Inc., and Samsung.</p>
</body></html>
"""


def test_html_to_text_drops_hidden_blocks_and_keeps_visible_text() -> None:
    text = html_to_text(HTML)
    assert "hidden" not in text
    assert "Visible paragraph one." in text
    assert "| Cell A | Cell B" in text
    assert "SK Hynix Inc., Micron Technology, Inc., and Samsung." in text


def test_split_sentences_respects_abbreviations_and_decimals() -> None:
    text = (
        "Apple Inc. accounted for approximately 16% of revenue. Sales grew 10.5% in fiscal 2025. "
        "Our key customers include Amazon, Apple Inc., and Bose. The U.S. market was flat."
    )
    sentences = [s for _, s in split_sentences(text)]
    assert sentences == [
        "Apple Inc. accounted for approximately 16% of revenue.",
        "Sales grew 10.5% in fiscal 2025.",
        "Our key customers include Amazon, Apple Inc., and Bose.",
        "The U.S. market was flat.",
    ]


def test_find_sections_skips_table_of_contents() -> None:
    toc = "| Item 1. | Business | 3\n| Item 1A. | Risk Factors | 9\n| Item 7. | Management's Discussion | 30\n"
    body = (
        "Item 1. Business\n"
        + "Apple designs things. " * 200
        + "\nItem 1A. Risk Factors\n"
        + "Risks abound. " * 300
        + "\nItem 7. Management's Discussion and Analysis\n"
        + "We discuss. " * 200
    )
    text = toc + body
    sections = find_sections(text)
    assert list(sections) == ["Item 1", "Item 1A", "Item 7"]
    assert sections["Item 1"][0] == len(toc)
    assert sections["Item 1"][1] == sections["Item 1A"][0] < sections["Item 7"][0]
