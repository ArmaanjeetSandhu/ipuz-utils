import argparse
import json
import sys

from shared import make_is_playable


def extract_fills(ipuz_file):
    """Extracts the list of fills (answer words) from an ipuz puzzle.

    Reads an .ipuz file's "solution" grid and walks each Across and Down
    entry, determined by standard crossword numbering rules on the
    "puzzle" grid, to reconstruct the actual letters that make up every
    fill in the puzzle.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A single alphabetically sorted list of uppercase fill strings,
        combining both Across and Down entries with no distinction
        between the two.

    Raises:
        SystemExit: If the file cannot be found, contains no puzzle
            grid, or contains no solution grid.
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

    solution = data.get("solution", [])
    if not solution:
        print("Error: No solution grid found in the file.")
        sys.exit(1)

    is_playable = make_is_playable(puzzle)

    rows = len(puzzle)
    cols = max(len(row) for row in puzzle) if rows > 0 else 0

    def letter_at(r, c):
        """Retrieves the uppercase solution letter at a grid cell.

        Args:
            r: Zero-indexed row coordinate.
            c: Zero-indexed column coordinate.

        Returns:
            The uppercase letter occupying the cell, or an empty
            string if the cell is missing or empty.
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

    across_fills = []
    down_fills = []

    for r in range(rows):
        for c in range(cols):
            if not is_playable(r, c):
                continue

            starts_across = not is_playable(r, c - 1) and is_playable(r, c + 1)
            starts_down = not is_playable(r - 1, c) and is_playable(r + 1, c)

            if starts_across:
                letters = []
                cc = c
                while is_playable(r, cc):
                    letters.append(letter_at(r, cc))
                    cc += 1
                across_fills.append("".join(letters))

            if starts_down:
                letters = []
                rr = r
                while is_playable(rr, c):
                    letters.append(letter_at(rr, c))
                    rr += 1
                down_fills.append("".join(letters))

    return sorted(across_fills + down_fills)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract the alphabetically sorted list of fills (answer words) from an ipuz crossword puzzle."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    fills = extract_fills(ipuz_file=args.ipuz_file)

    for fill in fills:
        print(fill)
