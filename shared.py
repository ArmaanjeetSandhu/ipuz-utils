"""Shared utilities."""


def make_is_playable(puzzle):
    """Returns an ``is_playable`` function bound to the given puzzle grid.

    The returned function determines whether a grid cell is a playable
    (white) square, i.e., within bounds, not None, and not a black
    square ("#").

    Args:
        puzzle: A 2-D list representing the crossword grid, as found
            in the ``"puzzle"`` key of an ipuz file.

    Returns:
        A callable ``is_playable(r, c) -> bool`` that accepts
        zero-indexed row and column coordinates.
    """
    rows = len(puzzle)
    cols = max(len(row) for row in puzzle) if rows > 0 else 0

    def is_playable(r, c):
        """Determines whether a grid cell is a playable (white) square.

        Args:
            r: Zero-indexed row coordinate.
            c: Zero-indexed column coordinate.

        Returns:
            True if the coordinate is within the grid bounds and the
            cell is neither None nor a black square ("#"); False
            otherwise.
        """
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return False

        try:
            cell = puzzle[r][c]
        except IndexError:
            return False

        if cell is None or cell == "#":
            return False

        return True

    return is_playable
