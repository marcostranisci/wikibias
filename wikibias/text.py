"""Shared text helpers."""


def clean_wikitext(wikitext: str) -> str:
    """Strip MediaWiki markup and return readable text.

    Templates are removed; link markup is stripped but the link text is kept,
    so names of linked people stay in the sentence.
    """
    import mwparserfromhell

    wikicode = mwparserfromhell.parse(wikitext)
    for template in wikicode.filter_templates(recursive=False):
        try:
            wikicode.remove(template)
        except ValueError:
            continue
    return str(wikicode.strip_code()).strip()
