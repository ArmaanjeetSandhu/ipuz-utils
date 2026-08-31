from shared import grid_dimensions, load_ipuz, make_is_playable, single_file_parser


def find_unchecked_squares(puzzle):
    """Finds "unchecked" squares in a crossword grid.

    An unchecked square (an "unch") is a playable square that is not
    part of both an Across word and a Down word, i.e., it lacks a
    playable neighbor in one of the two directions.

    Args:
        puzzle: A 2-D list representing the crossword grid.

    Returns:
        A list of 1-indexed ``(row, col)`` tuples identifying the
        unchecked squares. An empty list means every playable square is
        checked by both an Across and a Down word.
    """
    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)

    unchecked_squares = []

    for r in range(rows):
        for c in range(cols):
            if not is_playable(r, c):
                continue

            is_in_across_word = is_playable(r, c - 1) or is_playable(r, c + 1)
            is_in_down_word = is_playable(r - 1, c) or is_playable(r + 1, c)

            if not (is_in_across_word and is_in_down_word):
                unchecked_squares.append((r + 1, c + 1))

    return unchecked_squares


if __name__ == "__main__":
    parser = single_file_parser(
        'Find unchecked squares ("unches") in an ipuz crossword grid.'
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("puzzle",))

    uncheck_list = find_unchecked_squares(data["puzzle"])

    if not uncheck_list:
        print("✓ No unches found!")
    else:
        print(
            f"✗ Found {len(uncheck_list)} unchecked square(s) at the following coordinates:"
        )
        for r, c in uncheck_list:
            print(f"‣ Row {r}, Column {c}")
