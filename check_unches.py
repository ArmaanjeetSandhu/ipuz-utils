import argparse
import json
import sys

from shared import make_is_playable


def find_unchecked_squares(ipuz_file):
    """Finds "unchecked" squares in an ipuz crossword grid.

    An unchecked square (an "unch") is a playable square that is not
    part of both an Across word and a Down word — i.e., it lacks a
    playable neighbor in one of the two directions. This function reads
    an .ipuz file and identifies all such squares.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A list of 1-indexed ``(row, col)`` tuples identifying the
        unchecked squares. An empty list means every playable square is
        checked by both an Across and a Down word.

    Raises:
        SystemExit: If the file cannot be found or contains no puzzle
            grid.
    """
    try:
        with open(ipuz_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find the file '{ipuz_file}'")
        sys.exit(1)

    puzzle = data.get("puzzle", [])
    if not puzzle:
        print("Error: No puzzle grid found in the file.")
        sys.exit(1)

    is_playable = make_is_playable(puzzle)

    unchecked_squares = []

    rows = len(puzzle)
    cols = max(len(row) for row in puzzle) if rows > 0 else 0

    for r in range(rows):
        for c in range(cols):
            if not is_playable(r, c):
                continue

            left_is_playable = is_playable(r, c - 1)
            right_is_playable = is_playable(r, c + 1)
            is_in_across_word = left_is_playable or right_is_playable

            top_is_playable = is_playable(r - 1, c)
            bottom_is_playable = is_playable(r + 1, c)
            is_in_down_word = top_is_playable or bottom_is_playable

            if not (is_in_across_word and is_in_down_word):
                unchecked_squares.append((r + 1, c + 1))

    return unchecked_squares


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Find unchecked squares ("unches") in an ipuz crossword grid.'
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    uncheck_list = find_unchecked_squares(args.ipuz_file)

    if not uncheck_list:
        print("✓ No unches found!")
    else:
        print(
            f"✗ Found {len(uncheck_list)} unchecked square(s) at the following coordinates:"
        )
        for r, c in uncheck_list:
            print(f"   - Row {r}, Column {c}")
