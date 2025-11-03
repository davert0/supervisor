import re


_MARKDOWN_SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!\\"
_MARKDOWN_ESCAPE_PATTERN = re.compile(f"[{re.escape(_MARKDOWN_SPECIAL_CHARS)}]")


def escape_markdown(text) -> str:
    if text is None:
        return ""
    return _MARKDOWN_ESCAPE_PATTERN.sub(lambda match: "\\" + match.group(0), str(text))

