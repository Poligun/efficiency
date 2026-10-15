"""The one import root every Python target shares.

The import root is `python/`, so `python/ops/deploy/deploy.py` imports as
`ops.deploy.deploy` and mypy's `mypy_path` names the same directory. rules_py
resolves a relative `imports` entry against the declaring package, which
makes the right value depend on the package's depth: `..` from `python/ops`,
`../..` from `python/ops/deploy`. Computing it here keeps every package on
the one root instead of asking each BUILD file to count.
"""

_ROOT = "python"

def py_imports():
    """Returns the `imports` list that puts python/ on sys.path.

    Call it from a BUILD file under `python/<program>/`; it fails anywhere
    else, because no other tree shares the root.

    Returns:
        A one-element list holding the package-relative path to `python/`.
    """
    package = native.package_name()
    parts = package.split("/")
    if parts[0] != _ROOT or len(parts) < 2:
        fail("py_imports() is for packages under %s/<program>/, not //%s" % (_ROOT, package))
    return ["/".join([".."] * (len(parts) - 1))]
