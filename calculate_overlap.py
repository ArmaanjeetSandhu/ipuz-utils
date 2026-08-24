import argparse
import sys

from shared import grid_dimensions, letter_at, load_ipuz, make_is_playable


def calculate_overlap(puzzle_a, solution_a, puzzle_b, solution_b):
    """Calculates how many white squares hold the same letter in two grids.

    Compares two crosswords that are alternate fills of one another
    (i.e., they share an identical layout of black and white squares)
    by checking the solution letter in every white square, reporting how
    much of the fill the two puzzles have in common.

    Args:
        puzzle_a: The crossword grid of the first puzzle.
        solution_a: The solution grid of the first puzzle.
        puzzle_b: The crossword grid of the second puzzle.
        solution_b: The solution grid of the second puzzle.

    Returns:
        A tuple ``(matching, total_white, percentage)`` where ``matching``
        is the number of white squares holding the same letter in both grids,
        ``total_white`` is the total number of white squares, and ``percentage``
        is ``matching`` expressed as a float percentage (0-100) of ``total_white``.

    Raises:
        SystemExit: If the two grids have different dimensions or
            different black square placements (in which case they are
            not alternate fills of each other), or if the shared grid
            has no white squares.
    """
    rows_a, cols_a = grid_dimensions(puzzle_a)
    rows_b, cols_b = grid_dimensions(puzzle_b)

    if (rows_a, cols_a) != (rows_b, cols_b):
        print(
            "Error: The two puzzles have different dimensions "
            f"({cols_a}x{rows_a} vs {cols_b}x{rows_b})."
        )
        print("Alternate fills must share an identical layout.")
        sys.exit(1)

    is_playable_a = make_is_playable(puzzle_a)
    is_playable_b = make_is_playable(puzzle_b)

    layout_mismatches = [
        (r + 1, c + 1)
        for r in range(rows_a)
        for c in range(cols_a)
        if is_playable_a(r, c) != is_playable_b(r, c)
    ]

    if layout_mismatches:
        print(
            f"Error: The two grids differ in black square placement at "
            f"{len(layout_mismatches)} square(s):"
        )
        for r, c in layout_mismatches[:10]:
            print(f"‣ Row {r}, Column {c}")
        if len(layout_mismatches) > 10:
            print(f"... and {len(layout_mismatches) - 10} more.")
        print("Alternate fills must share an identical layout.")
        sys.exit(1)

    total_white = 0
    matching = 0

    for r in range(rows_a):
        for c in range(cols_a):
            if not is_playable_a(r, c):
                continue

            total_white += 1
            letter_a = letter_at(solution_a, r, c)
            letter_b = letter_at(solution_b, r, c)

            if letter_a == letter_b:
                matching += 1

    if total_white == 0:
        print("Error: The grid has no playable white squares.")
        sys.exit(1)

    percentage = (matching / total_white) * 100

    return matching, total_white, percentage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate the percentage of white squares that hold the same letter in two ipuz crosswords that are alternate fills of each other."
    )
    parser.add_argument("ipuz_file_a", help="Path to the first .ipuz file to read.")
    parser.add_argument("ipuz_file_b", help="Path to the second .ipuz file to read.")

    args = parser.parse_args()

    required = ("puzzle", "solution")
    data_a = load_ipuz(args.ipuz_file_a, require=required)
    data_b = load_ipuz(args.ipuz_file_b, require=required)

    same_count, white_count, percent = calculate_overlap(
        data_a["puzzle"], data_a["solution"], data_b["puzzle"], data_b["solution"]
    )

    print(f"White squares:  {white_count}")
    print(f"Same letter:    {same_count}")
    print(f"Different:      {white_count - same_count}")
    print(f"Overlap:        {percent:.2f}%")

    if same_count == white_count:
        print("✗ The two grids are identical.")
