import string
from collections import Counter

from shared import cell_value, load_ipuz, print_bar_chart, single_file_parser


def count_letter_frequencies(solution):
    """Counts letter frequencies in a puzzle's solution grid.

    Tallies how many times each uppercase letter A-Z appears in the
    solution grid. Solution cells may be plain strings or dicts with a
    "value" key; non-alphabetic characters (blocks, empty cells,
    punctuation) are ignored.

    Args:
        solution: A 2-D list representing the solution grid.

    Returns:
        A ``collections.Counter`` mapping each uppercase letter found to
        the number of times it appears in the solution grid.
    """
    letter_counts = Counter()

    for row in solution:
        for cell in row:
            char = cell_value(cell).strip().upper()
            if char.isalpha():
                letter_counts[char] += 1

    return letter_counts


if __name__ == "__main__":
    parser = single_file_parser(
        "Count letter frequencies in an ipuz crossword puzzle's solution grid."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("solution",))

    frequencies = count_letter_frequencies(data["solution"])

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
