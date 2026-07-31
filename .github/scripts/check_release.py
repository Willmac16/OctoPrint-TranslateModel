"""Check a release tag against the version in pyproject.toml.

    python .github/scripts/check_release.py 0.3.3

The software update plugin fetches archive/<tag>.zip and compares the tag to
the installed distribution's version, so a tag that disagrees with
pyproject.toml produces an update that either will not install or reports the
wrong version once it has. The version has historically been bumped in its own
commit, which is exactly the kind of step that gets forgotten.
"""

import sys
import tomllib


def main(argv):
    if len(argv) != 1:
        print("usage: check_release.py <tag>", file=sys.stderr)
        return 2

    tag = argv[0]
    # Tags in this repo are bare versions (0.3.2), matching the archive URL in
    # get_update_information(); tolerate a v prefix in case that ever changes.
    normalised = tag[1:] if tag.startswith("v") else tag

    with open("pyproject.toml", "rb") as handle:
        declared = tomllib.load(handle)["project"]["version"]

    if normalised != declared:
        print(
            "tag {} does not match pyproject.toml version {}".format(tag, declared),
            file=sys.stderr,
        )
        return 1

    print("tag {} matches pyproject.toml version {}".format(tag, declared))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
