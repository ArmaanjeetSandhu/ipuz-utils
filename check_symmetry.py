from shared import grid_dimensions, load_ipuz, make_is_playable, single_file_parser


def check_rotational_symmetry(puzzle):
    """Checks a puzzle grid for 180-degree rotational symmetry.

    Compares each cell with its 180-degree rotational counterpart (i.e.,
    the cell obtained by rotating the grid half a turn about its
    center), reporting any pairs where one cell is a block (or off-grid)
    and the other is not.

    Args:
        puzzle: A 2-D list representing the crossword grid.

    Returns:
        A list of mismatched pairs, where each element is a tuple of two
        1-indexed ``(row, col)`` coordinate tuples representing a cell
        and its rotationally opposite cell that do not match in
        block/white status. An empty list means the grid has perfect
        symmetry.
    """
    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)

    asymmetric_pairs = []

    for r in range(rows):
        for c in range(cols):
            if r > rows // 2 or (r == rows // 2 and c >= cols // 2):
                continue

            opposite_r = rows - 1 - r
            opposite_c = cols - 1 - c

            if is_playable(r, c) != is_playable(opposite_r, opposite_c):
                asymmetric_pairs.append(
                    ((r + 1, c + 1), (opposite_r + 1, opposite_c + 1))
                )

    return asymmetric_pairs


if __name__ == "__main__":
    parser = single_file_parser(
        "Check an ipuz crossword grid for 180-degree rotational symmetry."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("puzzle",))

    mismatches = check_rotational_symmetry(data["puzzle"])

    if not mismatches:
        print("✓ The puzzle has perfect 180° rotational symmetry!")
    else:
        print(
            f"✗ Symmetry broken! Found {len(mismatches)} mismatched pair(s) of squares:"
        )
        for (r1, c1), (r2, c2) in mismatches:
            print(
                f"   - Cell (Row {r1}, Col {c1}) does not match opposite Cell (Row {r2}, Col {c2})"
            )
