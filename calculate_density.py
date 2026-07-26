import argparse
import json
import sys


def calculate_black_square_percentage(ipuz_file):
    """Calculates the percentage of black squares in an ipuz puzzle grid.

    Reads an .ipuz file, iterates over every cell in the puzzle grid, and
    computes what fraction of cells are black squares (represented by "#").

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A tuple ``(black_squares, total_squares, percentage)`` where
        ``black_squares`` is the count of black squares, ``total_squares``
        is the total number of cells in the grid, and ``percentage`` is
        the black square density expressed as a float percentage
        (0-100).

    Raises:
        SystemExit: If the file cannot be found, contains no puzzle grid,
            or the puzzle grid is empty.
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

    total_squares = 0
    black_squares = 0

    for row in puzzle:
        for cell in row:
            total_squares += 1
            if cell == "#":
                black_squares += 1

    if total_squares == 0:
        print("Error: The puzzle grid is completely empty.")
        sys.exit(1)

    percentage = (black_squares / total_squares) * 100

    return black_squares, total_squares, percentage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate the percentage of black squares in an ipuz crossword grid."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    black_count, total_count, percent = calculate_black_square_percentage(
        args.ipuz_file
    )

    print(f"Total squares: {total_count}")
    print(f"Black squares: {black_count}")
    print(f"Density:       {percent:.2f}%")
