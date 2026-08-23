import argparse
import json
import sys
from collections import Counter

from shared import make_is_playable


def count_puzzle_fills(ipuz_file):
    """Counts the number of Across and Down fills in an ipuz puzzle.

    Reads an .ipuz file and counts the number of clue entries listed
    under the "Across" and "Down" sections of the puzzle's clues.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A tuple ``(across_fills, down_fills, total_fills)`` containing
        the number of Across clues, the number of Down clues, and their
        sum.

    Raises:
        SystemExit: If the file cannot be found or contains no clues.
    """
    try:
        with open(ipuz_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find the file '{ipuz_file}'")
        sys.exit(1)

    clues = data.get("clues", {})
    if not clues:
        print("Error: No clues found in the file.")
        sys.exit(1)

    across_fills = len(clues.get("Across", []))
    down_fills = len(clues.get("Down", []))
    total_fills = across_fills + down_fills

    return across_fills, down_fills, total_fills


def count_fill_lengths(ipuz_file):
    """Counts how many fills exist of each length in an ipuz puzzle.

    Reads an .ipuz file's "puzzle" grid and walks each Across and Down
    entry, determined by standard crossword numbering rules, to tally
    how many fills exist for each fill length.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A ``collections.Counter`` mapping each fill length found to the
        number of fills of that length.

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

    rows = len(puzzle)
    cols = max(len(row) for row in puzzle) if rows > 0 else 0

    length_counts = Counter()

    for r in range(rows):
        for c in range(cols):
            if not is_playable(r, c):
                continue

            starts_across = not is_playable(r, c - 1) and is_playable(r, c + 1)
            starts_down = not is_playable(r - 1, c) and is_playable(r + 1, c)

            if starts_across:
                length = 0
                cc = c
                while is_playable(r, cc):
                    length += 1
                    cc += 1
                length_counts[length] += 1

            if starts_down:
                length = 0
                rr = r
                while is_playable(rr, c):
                    length += 1
                    rr += 1
                length_counts[length] += 1

    return length_counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Count the number of Across and Down fills in an ipuz crossword puzzle."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    length_counts = count_fill_lengths(args.ipuz_file)

    if not length_counts:
        print("No fills were found in the puzzle grid.")
    else:
        sorted_lengths = sorted(length_counts.items(), key=lambda x: (-x[1], x[0]))
        max_count = max(length_counts.values())
        max_bar_width = 40
        scale = max_bar_width / max_count if max_count > max_bar_width else 1

        print("-" * 55)
        for length, count in sorted_lengths:
            bar = "█" * max(1, round(count * scale))
            print(f"Length {length:2} : {count:2} | {bar}")
        print("-" * 55)

    across, down, total = count_puzzle_fills(args.ipuz_file)

    print(f"Total: {total} ({across} Across, {down} Down)")
