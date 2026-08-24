from shared import grid_dimensions, load_ipuz, make_is_playable, single_file_parser

SQUARE_ONLY = "square-only"

SYMMETRIES = (
    {
        "key": "diagonal",
        "label": "Symmetry about the diagonal",
        "square_only": True,
        "transform": lambda r, c, rows, cols: (c, r),
    },
    {
        "key": "antidiagonal",
        "label": "Symmetry about the anti-diagonal",
        "square_only": True,
        "transform": lambda r, c, rows, cols: (cols - 1 - c, rows - 1 - r),
    },
    {
        "key": "vertical",
        "label": "Vertical mirror symmetry",
        "square_only": False,
        "transform": lambda r, c, rows, cols: (r, cols - 1 - c),
    },
    {
        "key": "horizontal",
        "label": "Horizontal mirror symmetry",
        "square_only": False,
        "transform": lambda r, c, rows, cols: (rows - 1 - r, c),
    },
    {
        "key": "rot180",
        "label": "180° rotational symmetry",
        "square_only": False,
        "transform": lambda r, c, rows, cols: (rows - 1 - r, cols - 1 - c),
    },
    {
        "key": "rot90",
        "label": "90° rotational symmetry",
        "square_only": True,
        "transform": lambda r, c, rows, cols: (c, rows - 1 - r),
    },
)

_GROUP_NAMES = {
    frozenset(): "no symmetry at all",
    frozenset({"rot180"}): "180° rotational symmetry only",
    frozenset({"vertical"}): "a single mirror line (vertical)",
    frozenset({"horizontal"}): "a single mirror line (horizontal)",
    frozenset({"diagonal"}): "a single mirror line (the diagonal)",
    frozenset({"antidiagonal"}): "a single mirror line (the anti-diagonal)",
    frozenset({"vertical", "horizontal", "rot180"}): "both straight mirror lines",
    frozenset({"diagonal", "antidiagonal", "rot180"}): "both diagonal mirror lines",
    frozenset({"rot90", "rot180"}): "quarter-turn rotation, but no mirror line",
    frozenset(
        {
            "diagonal",
            "antidiagonal",
            "vertical",
            "horizontal",
            "rot180",
            "rot90",
        }
    ): "the full symmetry of the square",
}


def has_symmetry(puzzle, transform):
    """Checks a puzzle grid against a single symmetry transformation.

    Compares each cell with the cell it is mapped to by ``transform``,
    looking for any pair where one cell is a block (or off-grid) and the
    other is not. Returns as soon as such a pair is found.

    Args:
        puzzle: A 2-D list representing the crossword grid.
        transform: A callable ``transform(r, c, rows, cols)`` returning
            the zero-indexed ``(row, col)`` coordinate that the cell at
            zero-indexed ``(r, c)`` is mapped to by the symmetry.

    Returns:
        True if every cell matches its counterpart in block/white
        status, meaning the grid has this symmetry; False otherwise.
    """
    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)

    for r in range(rows):
        for c in range(cols):
            opposite_r, opposite_c = transform(r, c, rows, cols)

            if is_playable(r, c) != is_playable(opposite_r, opposite_c):
                return False

    return True


def find_symmetries(puzzle):
    """Checks a puzzle grid against every symmetry a crossword can have.

    Tests the four reflections (vertical, horizontal, diagonal and
    anti-diagonal) and the two rotations (180° and 90°).
    The diagonal reflections and the 90° rotation swap the width
    and height of the grid, so they are only applicable when the grid is
    square; for a non-square grid they are reported as such rather than
    as failures.

    Args:
        puzzle: A 2-D list representing the crossword grid.

    Returns:
        A list of dictionaries in the order the symmetries are defined,
        each with keys ``"key"``, ``"label"`` and ``"holds"`` (True,
        False, or the string ``"square-only"`` if the symmetry cannot
        apply to this grid's shape).
    """
    rows, cols = grid_dimensions(puzzle)
    is_square = rows == cols

    results = []

    for symmetry in SYMMETRIES:
        if symmetry["square_only"] and not is_square:
            holds = SQUARE_ONLY
        else:
            holds = has_symmetry(puzzle, symmetry["transform"])

        results.append(
            {
                "key": symmetry["key"],
                "label": symmetry["label"],
                "holds": holds,
            }
        )

    return results


def describe_symmetry_group(results):
    """Names the overall symmetry a grid possesses.

    Args:
        results: The list of per-symmetry results returned by
            ``find_symmetries``.

    Returns:
        A short human-readable description of the combined symmetry.
    """
    held = frozenset(r["key"] for r in results if r["holds"] is True)
    return _GROUP_NAMES.get(held, "an unexpected combination of symmetries")


if __name__ == "__main__":
    parser = single_file_parser(
        "Report every symmetry that an ipuz crossword grid possesses."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("puzzle",))

    symmetry_results = find_symmetries(data["puzzle"])

    width = max(len(s["label"]) for s in SYMMETRIES)

    for result in symmetry_results:
        if result["holds"] is SQUARE_ONLY:
            print(
                f"✗ {result['label']:<{width}}  (Not possible, since the grid is not square)"
            )
        elif result["holds"]:
            print(f"✓ {result['label']:<{width}}")
        else:
            print(f"✗ {result['label']:<{width}}")

    print(f"This grid has {describe_symmetry_group(symmetry_results)}.")
