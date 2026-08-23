from shared import extract_entries, letter_at, load_ipuz, single_file_parser


def extract_fills(puzzle, solution):
    """Extracts the list of fills (answer words) from an ipuz puzzle.

    Walks each Across and Down entry, determined by standard crossword
    numbering rules on the ``puzzle`` grid, to reconstruct the actual
    letters that make up every fill in the puzzle.

    Args:
        puzzle: A 2-D list representing the crossword grid.
        solution: A 2-D list representing the solution grid.

    Returns:
        A single alphabetically sorted list of uppercase fill strings,
        combining both Across and Down entries with no distinction
        between the two.
    """
    return sorted(
        "".join(letter_at(solution, r, c) for r, c in entry["cells"])
        for entry in extract_entries(puzzle)
    )


if __name__ == "__main__":
    parser = single_file_parser(
        "Extract the alphabetically sorted list of fills (answer words) from an ipuz crossword puzzle."
    )
    args = parser.parse_args()

    data = load_ipuz(args.ipuz_file, require=("puzzle", "solution"))

    for fill in extract_fills(data["puzzle"], data["solution"]):
        print(fill)
