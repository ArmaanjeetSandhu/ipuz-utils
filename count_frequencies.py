import string
from collections import Counter

from shared import (
    BLOCK,
    EMPTY,
    MULTI_VALUES,
    cell_value,
    load_ipuz,
    markers,
    print_bar_chart,
    single_file_parser,
)


def count_letter_frequencies(solution, block=BLOCK, empty=EMPTY):
    """Counts letter frequencies in a puzzle's solution grid.

    Tallies how many times each uppercase letter A-Z appears in the
    solution grid. Solution cells may be plain strings or dicts with a
    "value" key; non-alphabetic characters (blocks, empty cells,
    punctuation) are ignored. A cell holding several letters (a rebus)
    contributes each of them.

    Args:
        solution: A 2-D list representing the solution grid.
        block: The file's ``"block"`` marker.
        empty: The file's ``"empty"`` marker.

    Returns:
        A ``collections.Counter`` mapping each uppercase letter found to
        the number of times it appears in the solution grid.
    """
    letter_counts = Counter()

    for row in solution:
        for cell in row:
            for char in cell_value(cell, block, empty).upper():
                if char.isalpha():
                    letter_counts[char] += 1

    return letter_counts


if __name__ == "__main__":
    parser = single_file_parser(
        "Count letter frequencies in an ipuz crossword puzzle's solution grid."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("solution",), reject=(MULTI_VALUES,))

    frequencies = count_letter_frequencies(data["solution"], *markers(data))

    if not frequencies:
        print("No letters were found in the solution grid.")
    else:
        sorted_freq = sorted(frequencies.items(), key=lambda x: (-x[1], x[0]))

        print_bar_chart(
            ((f"   {letter}", count) for letter, count in sorted_freq),
            rule_width=45,
        )
        print(f"Total count: {sum(frequencies.values())}")

        found_letters = set(frequencies.keys())
        missing_letters = sorted(set(string.ascii_uppercase) - found_letters)

        if not missing_letters:
            print("This puzzle uses every letter of the alphabet.")
        else:
            print(f"Missing letters: {', '.join(missing_letters)}")
