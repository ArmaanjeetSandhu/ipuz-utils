import sys
from collections import deque

from shared import grid_dimensions, load_ipuz, make_is_playable, single_file_parser


def check_all_over_interlock(puzzle):
    """Checks whether all white squares in a grid form one connected region.

    Performs a breadth-first search over the white (playable) squares,
    treating orthogonally adjacent white squares as connected, to
    determine whether the grid exhibits "all-over interlock" (i.e.,
    every white square can be reached from every other white square).

    Args:
        puzzle: A 2-D list representing the crossword grid.

    Returns:
        A tuple ``(components, total_white)`` where ``components`` is the
        number of disconnected regions of white squares found (1 means
        perfect interlock) and ``total_white`` is the total number of
        white squares in the grid.

    Raises:
        SystemExit: If the grid has no playable white squares.
    """
    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)

    white_squares = {
        (r, c) for r in range(rows) for c in range(cols) if is_playable(r, c)
    }

    if not white_squares:
        print("Error: The grid has no playable white squares.")
        sys.exit(1)

    unvisited = set(white_squares)
    components = 0

    while unvisited:
        components += 1
        queue = deque([unvisited.pop()])

        while queue:
            curr_r, curr_c = queue.popleft()

            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor = (curr_r + dr, curr_c + dc)

                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    queue.append(neighbor)

    return components, len(white_squares)


if __name__ == "__main__":
    parser = single_file_parser(
        "Check whether all white squares in an ipuz crossword grid form one connected region."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("puzzle",))

    component_count, total_white = check_all_over_interlock(data["puzzle"])

    if component_count == 1:
        print("✓ The puzzle has perfect all-over interlock!")
        print(
            f"All {total_white} white squares are connected in a single continuous grid."
        )
    else:
        print("✗ Interlock broken!")
        print(f"The grid is fractured into {component_count} isolated sections.")
        print("Solvers would not be able to reach every part of the puzzle.")
