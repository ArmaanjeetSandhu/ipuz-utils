import sys

from shared import BLOCK, load_ipuz, single_file_parser


def calculate_black_square_percentage(puzzle):
    """Calculates the percentage of black squares in an ipuz puzzle grid.

    Iterates over every cell in the puzzle grid and computes what
    fraction of cells are black squares (represented by "#").

    Args:
        puzzle: A 2-D list representing the crossword grid.

    Returns:
        A tuple ``(black_squares, total_squares, percentage)`` where
        ``black_squares`` is the count of black squares, ``total_squares``
        is the total number of cells in the grid, and ``percentage`` is
        the black square density expressed as a float percentage
        (0-100).

    Raises:
        SystemExit: If the puzzle grid is empty.
    """
    total_squares = 0
    black_squares = 0

    for row in puzzle:
        for cell in row:
            total_squares += 1
            if cell == BLOCK:
                black_squares += 1

    if total_squares == 0:
        print("Error: The puzzle grid is completely empty.")
        sys.exit(1)

    percentage = (black_squares / total_squares) * 100

    return black_squares, total_squares, percentage


if __name__ == "__main__":
    parser = single_file_parser(
        "Calculate the percentage of black squares in an ipuz crossword grid."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("puzzle",))

    black_count, total_count, percent = calculate_black_square_percentage(
        data["puzzle"]
    )

    print(f"Total squares: {total_count}")
    print(f"Black squares: {black_count}")
    print(f"Density:       {percent:.2f}%")
