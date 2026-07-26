import argparse
import json
import sys


def check_all_over_interlock(ipuz_file):
    """Checks whether all white squares in an ipuz grid form one connected region.

    Reads an .ipuz file and performs a breadth-first search over the
    white (playable) squares, treating orthogonally adjacent white
    squares as connected, to determine whether the grid exhibits
    "all-over interlock" (i.e., every white square can be reached from
    every other white square).

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A tuple ``(components, total_white)`` where ``components`` is the
        number of disconnected regions of white squares found (1 means
        perfect interlock) and ``total_white`` is the total number of
        white squares in the grid.

    Raises:
        SystemExit: If the file cannot be found, contains no puzzle grid,
            or has no playable white squares.
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

    rows = len(puzzle)
    cols = max(len(row) for row in puzzle) if rows > 0 else 0

    white_squares = set()
    for r in range(rows):
        for c in range(cols):
            try:
                cell = puzzle[r][c]
                if cell != "#" and cell is not None:
                    white_squares.add((r, c))
            except IndexError:
                pass

    if not white_squares:
        print("Error: The grid has no playable white squares.")
        sys.exit(1)

    unvisited = set(white_squares)
    components = 0

    while unvisited:
        components += 1
        start_node = unvisited.pop()
        queue = [start_node]

        while queue:
            curr_r, curr_c = queue.pop(0)

            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = (curr_r + dr, curr_c + dc)

                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    queue.append(neighbor)

    return components, len(white_squares)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check whether all white squares in an ipuz crossword grid form one connected region."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    component_count, total_white = check_all_over_interlock(args.ipuz_file)

    if component_count == 1:
        print("✓ The puzzle has perfect all-over interlock!")
        print(
            f"All {total_white} white squares are connected in a single continuous grid."
        )
    else:
        print("✗ Interlock broken!")
        print(f"The grid is fractured into {component_count} isolated sections.")
        print("Solvers would not be able to reach every part of the puzzle.")
