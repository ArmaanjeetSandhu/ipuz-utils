from shared import (
    BARS,
    BLOCK,
    CLUE_CELLS,
    EMPTY,
    MULTI_VALUES,
    OTHER_DIRECTIONS,
    extract_entries,
    letter_at,
    load_ipuz,
    markers,
    single_file_parser,
)


def extract_fills(puzzle, solution, block=BLOCK, empty=EMPTY):
    """Extracts the list of fills from an ipuz puzzle.

    Walks each Across and Down entry, determined by standard crossword
    numbering rules on the ``puzzle`` grid, to reconstruct the actual
    letters that make up every fill in the puzzle.

    Args:
        puzzle: A 2-D list representing the crossword grid.
        solution: A 2-D list representing the solution grid.
        block: The file's ``"block"`` marker.
        empty: The file's ``"empty"`` marker.

    Returns:
        A single alphabetically sorted list of uppercase fill strings,
        combining both Across and Down entries with no distinction
        between the two.
    """
    return sorted(
        "".join(letter_at(solution, r, c, block, empty) for r, c in entry["cells"])
        for entry in extract_entries(puzzle, block)
    )


if __name__ == "__main__":
    parser = single_file_parser(
        "Extract the alphabetically sorted list of fills from an ipuz crossword puzzle."
    )
    args = parser.parse_args()

    data = load_ipuz(
        args.ipuz_file,
        require=("puzzle", "solution"),
        reject=(BARS, MULTI_VALUES),
        warn={
            OTHER_DIRECTIONS: "their fills are not listed",
            CLUE_CELLS: "only fills read Across and Down from the grid are listed",
        },
    )

    for fill in extract_fills(data["puzzle"], data["solution"], *markers(data)):
        print(fill)
