"""Label list helpers for the Python macros."""

# buildifier: disable=unnamed-macro
# buildifier treats any function that calls native.* as a macro and asks
# for a `name` argument; package_relative_label only converts strings to
# Labels and declares nothing, so this is a plain helper.
def dedupe_labels(labels):
    """Returns `labels` as canonical Labels with duplicates removed, order kept.

    The macros add implied dependencies (pytest, coverage, the mypy runner)
    to lists callers write by hand, and Bazel rejects a dependency listed
    twice even when the two spellings differ (`:foo` against
    `//pkg:foo`). Comparing canonical labels makes every spelling one entry.

    Args:
        labels: Strings or Labels, in any spelling.

    Returns:
        A list of Labels, first occurrence wins.
    """
    seen = {}
    for label in labels:
        seen[native.package_relative_label(label)] = None
    return list(seen.keys())
