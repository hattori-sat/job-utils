from typing import Tuple


def three_way_merge(base: str, local: str, remote: str) -> Tuple[str, bool]:
    """Merge whole-document bodies while preserving an explicit conflict."""

    if local == remote:
        return local, False
    if local == base:
        return remote, False
    if remote == base:
        return local, False
    merged = "<<<<<<< local\n{}=======\n{}>>>>>>> external\n".format(
        local.rstrip("\n") + "\n", remote.rstrip("\n") + "\n"
    )
    return merged, True
