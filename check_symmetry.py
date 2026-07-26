import argparse
import json
import sys


def check_rotational_symmetry(ipuz_file):
    """Checks an ipuz puzzle grid for 180-degree rotational symmetry.

    Reads an .ipuz file and compares each cell with its 180-degree
    rotational counterpart (i.e., the cell obtained by rotating the grid
    half a turn about its center), reporting any pairs where one cell is
    a block (or off-grid) and the other is not.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A list of mismatched pairs, where each element is a tuple of two
        1-indexed ``(row, col)`` coordinate tuples representing a cell
        and its rotationally opposite cell that do not match in
        block/white status. An empty list means the grid has perfect
        symmetry.

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

    rows = len(puzzle)
    cols = max(len(row) for row in puzzle) if rows > 0 else 0

    def is_block(r, c):
        """Determines whether a grid cell is a block (or off-grid) square.

        Args:
            r: Zero-indexed row coordinate.
            c: Zero-indexed column coordinate.

        Returns:
            True if the coordinate is outside the grid bounds, or if the
            cell at that coordinate is a black square ("#") or None;
            False otherwise.
        """
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return True
        try:
            cell = puzzle[r][c]
        except IndexError:
            return True

        return cell == "#" or cell is None

    asymmetric_pairs = []

    for r in range(rows):
        for c in range(cols):
            if r > rows // 2 or (r == rows // 2 and c >= cols // 2):
                continue

            opposite_r = rows - 1 - r
            opposite_c = cols - 1 - c

            if is_block(r, c) != is_block(opposite_r, opposite_c):
                asymmetric_pairs.append(
                    ((r + 1, c + 1), (opposite_r + 1, opposite_c + 1))
                )

    return asymmetric_pairs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check an ipuz crossword grid for 180-degree rotational symmetry."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    mismatches = check_rotational_symmetry(args.ipuz_file)

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
