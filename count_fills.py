import argparse
import json
import sys


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Count the number of Across and Down fills in an ipuz crossword puzzle."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    across, down, total = count_puzzle_fills(args.ipuz_file)

    print(f"Across: {across}")
    print(f"Down:   {down}")
    print(f"Total:  {total}")
