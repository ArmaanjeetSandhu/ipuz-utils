import argparse
import json
import sys

from shared import make_is_playable


def load_grids(ipuz_file):
    """Loads the puzzle and solution grids from an ipuz file.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A tuple ``(puzzle, solution)`` containing the 2-D puzzle grid
        and the 2-D solution grid.

    Raises:
        SystemExit: If the file cannot be found, cannot be parsed, or
            lacks a puzzle or solution grid.
    """
    try:
        with open(ipuz_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find the file '{ipuz_file}'")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: '{ipuz_file}' is not valid JSON ({exc}).")
        sys.exit(1)

    puzzle = data.get("puzzle", [])
    if not puzzle:
        print(f"Error: No puzzle grid found in '{ipuz_file}'.")
        sys.exit(1)

    solution = data.get("solution", [])
    if not solution:
        print(f"Error: No solution grid found in '{ipuz_file}'.")
        sys.exit(1)

    return puzzle, solution


def letter_at(solution, r, c):
    """Retrieves the uppercase solution letter at a grid cell.

    Args:
        solution: A 2-D list representing the solution grid.
        r: Zero-indexed row coordinate.
        c: Zero-indexed column coordinate.

    Returns:
        The uppercase letter occupying the cell, or an empty string if
        the cell is missing or empty.
    """
    try:
        cell = solution[r][c]
    except IndexError:
        return ""

    if cell is None or cell == "#":
        return ""

    if isinstance(cell, dict):
        cell = cell.get("value", "")

    return str(cell).upper()


def calculate_overlap(ipuz_file_a, ipuz_file_b):
    """Calculates how many white squares hold the same letter in two grids.

    Reads two .ipuz files that are alternate fills of one another (i.e.,
    they share an identical layout of black and white squares) and
    compares the solution letter in every white square, reporting how
    much of the fill the two puzzles have in common.

    Args:
        ipuz_file_a: Path to the first .ipuz file to read.
        ipuz_file_b: Path to the second .ipuz file to read.

    Returns:
        A tuple ``(matching, total_white, percentage, differences)``
        where ``matching`` is the number of white squares holding the
        same letter in both grids, ``total_white`` is the total number
        of white squares, ``percentage`` is ``matching`` expressed as a
        float percentage (0-100) of ``total_white``, and ``differences``
        is a list of ``(row, col, letter_a, letter_b)`` tuples, with
        1-indexed coordinates, for the squares that differ.

    Raises:
        SystemExit: If either file cannot be read, if the two grids have
            different dimensions or different black square placements
            (in which case they are not alternate fills of each other),
            or if the shared grid has no white squares.
    """
    puzzle_a, solution_a = load_grids(ipuz_file_a)
    puzzle_b, solution_b = load_grids(ipuz_file_b)

    rows_a = len(puzzle_a)
    cols_a = max(len(row) for row in puzzle_a) if rows_a > 0 else 0
    rows_b = len(puzzle_b)
    cols_b = max(len(row) for row in puzzle_b) if rows_b > 0 else 0

    if (rows_a, cols_a) != (rows_b, cols_b):
        print(
            "Error: The two puzzles have different dimensions "
            f"({cols_a}x{rows_a} vs {cols_b}x{rows_b})."
        )
        print("Alternate fills must share an identical layout.")
        sys.exit(1)

    is_playable_a = make_is_playable(puzzle_a)
    is_playable_b = make_is_playable(puzzle_b)

    layout_mismatches = []
    for r in range(rows_a):
        for c in range(cols_a):
            if is_playable_a(r, c) != is_playable_b(r, c):
                layout_mismatches.append((r + 1, c + 1))

    if layout_mismatches:
        print(
            f"Error: The two grids differ in black square placement at "
            f"{len(layout_mismatches)} square(s):"
        )
        for r, c in layout_mismatches[:10]:
            print(f"   - Row {r}, Column {c}")
        if len(layout_mismatches) > 10:
            print(f"   ... and {len(layout_mismatches) - 10} more.")
        print("Alternate fills must share an identical layout.")
        sys.exit(1)

    total_white = 0
    matching = 0
    differences = []

    for r in range(rows_a):
        for c in range(cols_a):
            if not is_playable_a(r, c):
                continue

            total_white += 1
            letter_a = letter_at(solution_a, r, c)
            letter_b = letter_at(solution_b, r, c)

            if letter_a == letter_b:
                matching += 1
            else:
                differences.append((r + 1, c + 1, letter_a, letter_b))

    if total_white == 0:
        print("Error: The grid has no playable white squares.")
        sys.exit(1)

    percentage = (matching / total_white) * 100

    return matching, total_white, percentage, differences


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate the percentage of white squares that hold the same letter in two ipuz crosswords that are alternate fills of each other."
    )
    parser.add_argument("ipuz_file_a", help="Path to the first .ipuz file to read.")
    parser.add_argument("ipuz_file_b", help="Path to the second .ipuz file to read.")
    parser.add_argument(
        "--show-differences",
        action="store_true",
        help="List every white square whose letter differs between the two grids.",
    )

    args = parser.parse_args()

    same_count, white_count, percent, diffs = calculate_overlap(
        args.ipuz_file_a, args.ipuz_file_b
    )

    print(f"White squares:  {white_count}")
    print(f"Same letter:    {same_count}")
    print(f"Different:      {white_count - same_count}")
    print(f"Overlap:        {percent:.2f}%")

    if args.show_differences and diffs:
        print("\nDiffering squares:")
        for r, c, letter_a, letter_b in diffs:
            print(f"   - Row {r}, Column {c}: {letter_a} vs {letter_b}")

    print()
    if same_count == white_count:
        print("✗ The two grids are identical — this is not an alternate fill.")
    elif same_count == 0:
        print("✓ Every single white square differs! A fully disjoint alternate fill.")
    else:
        print(f"The two fills share {percent:.2f}% of their letters.")
