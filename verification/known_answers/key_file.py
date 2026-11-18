"""The one parser for answer_key.sql. score.py (which runs the keys) and append_only.py (which fingerprints them) both use
it, so a header one of them reads as a boundary can never be ignored by the other.

Format: an optional comment preamble, then blocks. Each block starts with a header line that is exactly `-- q<digits>`
(no indent, one space, nothing after). A line that looks like a header but is not exactly that (`--q25`, `-- q25 x`,
`  -- q25`) is an error, a repeated id is an error, and SQL before the first header is an error.
"""
import re
import yaml

HEADER = re.compile(r"-- (q\d+)")
LOOKS_LIKE_HEADER = re.compile(r"\s*--\s*q\d+(?!\w)", re.I)


class KeyFileError(ValueError):
    pass


def parse(text):
    """{qid: [body lines]} in file order. Raises KeyFileError on a malformed or repeated header."""
    blocks, cur = {}, None
    for n, line in enumerate(text.splitlines(), 1):
        m = HEADER.fullmatch(line)
        if m:
            cur = m.group(1)
            if cur in blocks:
                raise KeyFileError(f"answer_key.sql line {n}: second header for {cur}")
            blocks[cur] = []
        elif LOOKS_LIKE_HEADER.match(line):
            raise KeyFileError(f"answer_key.sql line {n}: {line.strip()!r} looks like a header but is not exactly '-- qNN'")
        elif cur is None:
            if line.strip() and not line.strip().startswith("--"):
                raise KeyFileError(f"answer_key.sql line {n}: SQL before the first '-- qNN' header")
        else:
            blocks[cur].append(line)
    return blocks


def queries(text):
    """{qid: sql} as score.py runs it (comments kept, DuckDB ignores them)"""
    return {k: "\n".join(v).strip() for k, v in parse(text).items()}


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _no_duplicates(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise KeyFileError(f"duplicate key {key!r} at line {k.start_mark.line + 1}: a plain YAML loader keeps only the last one")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def load_yaml(text):
    """yaml.safe_load that refuses a mapping with the same key twice (question files, answer files)"""
    return yaml.load(text, Loader=_UniqueKeyLoader)
