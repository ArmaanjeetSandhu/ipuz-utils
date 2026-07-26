import argparse
import json
import sys
import string
from collections import Counter


def count_letter_frequencies(ipuz_file):
    """Counts letter frequencies in an ipuz puzzle's solution grid.

    Reads an .ipuz file and tallies how many times each uppercase letter
    A-Z appears in the solution grid. Solution cells may be plain
    strings or dicts with a "value" key; non-alphabetic characters
    (blocks, empty cells, punctuation) are ignored.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        A ``collections.Counter`` mapping each uppercase letter found to
        the number of times it appears in the solution grid.

    Raises:
        SystemExit: If the file cannot be found or contains no solution
            grid.
    """
    try:
        with open(ipuz_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find the file '{ipuz_file}'")
        sys.exit(1)

    solution = data.get("solution", [])
    if not solution:
        print("Error: No solution grid found in the file.")
        sys.exit(1)

    letter_counts = Counter()

    for row in solution:
        for cell in row:
            char = ""

            if isinstance(cell, dict):
                char = cell.get("value", "")
            elif isinstance(cell, str):
                char = cell

            char = char.strip().upper()
            if char.isalpha():
                letter_counts[char] += 1

    return letter_counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Count letter frequencies in an ipuz crossword puzzle's solution grid."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")

    args = parser.parse_args()

    frequencies = count_letter_frequencies(args.ipuz_file)

    if not frequencies:
        print("No letters were found in the solution grid.")
    else:
        sorted_freq = sorted(frequencies.items(), key=lambda x: (-x[1], x[0]))

        print("-" * 45)
        for letter, count in sorted_freq:
            bar = "█" * count
            print(f"   {letter} : {count:2} | {bar}")
        print("-" * 45)
        print(f"Total count: {sum(frequencies.values())}")

        alphabet = set(string.ascii_uppercase)
        found_letters = set(frequencies.keys())
        missing_letters = sorted(alphabet - found_letters)

        if len(found_letters) == 26:
            print("This puzzle uses every letter of the alphabet.")
        else:
            print(f"Missing letters: {', '.join(missing_letters)}")
