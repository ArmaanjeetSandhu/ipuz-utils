from collections import Counter

from shared import (
    BARS,
    BLOCK,
    CLUE_CELLS,
    OTHER_DIRECTIONS,
    clue_group,
    extract_entries,
    load_ipuz,
    markers,
    print_bar_chart,
    single_file_parser,
)


def count_clue_fills(clues):
    """Counts the number of Across and Down fills clued in a puzzle.

    The clue lists are found whatever heading the file gives them, so
    ``"Across:Horizontales"`` counts as Across. A clue shared by several
    entries, listed under a ``"numbers"`` key, counts once per entry.

    Args:
        clues: The ``"clues"`` mapping from an ipuz file.

    Returns:
        A tuple ``(across_fills, down_fills, total_fills)`` containing
        the number of Across fills clued, the number of Down fills
        clued, and their sum.
    """

    def count(direction):
        _, group = clue_group(clues, direction)
        return sum(
            (
                len(clue["numbers"])
                if isinstance(clue, dict) and clue.get("numbers")
                else 1
            )
            for clue in group
        )

    across_fills = count("Across")
    down_fills = count("Down")

    return across_fills, down_fills, across_fills + down_fills


def count_fill_lengths(puzzle, block=BLOCK):
    """Counts how many fills exist of each length in a puzzle grid.

    Walks each Across and Down entry, determined by standard crossword
    numbering rules, to tally how many fills exist for each fill length.

    Args:
        puzzle: A 2-D list representing the crossword grid.
        block: The file's ``"block"`` marker. Defaults to the ipuz
            default of ``"#"``.

    Returns:
        A ``collections.Counter`` mapping each fill length found to the
        number of fills of that length.
    """
    return Counter(len(entry["cells"]) for entry in extract_entries(puzzle, block))


def find_short_entries(puzzle, block=BLOCK):
    """Finds every entry in a puzzle grid shorter than three squares.

    Args:
        puzzle: A 2-D list representing the crossword grid.
        block: The file's ``"block"`` marker. Defaults to the ipuz
            default of ``"#"``.

    Returns:
        A list of ``(direction, row, col)`` tuples in grid reading
        order, where ``row`` and ``col`` are the zero-indexed
        coordinates of the entry's first cell.
    """
    short_entries = []

    for entry in extract_entries(puzzle, block):
        if len(entry["cells"]) >= 3:
            continue

        row, col = entry["cells"][0]
        short_entries.append((entry["direction"], row, col))

    return short_entries


if __name__ == "__main__":
    parser = single_file_parser(
        "Count the number of Across and Down fills in an ipuz crossword puzzle."
    )
    args = parser.parse_args()

    data = load_ipuz(
        args.ipuz_file,
        require=("puzzle", "clues"),
        reject=(BARS,),
        warn={
            OTHER_DIRECTIONS: "not counted",
            CLUE_CELLS: "counted as ordinary Across and Down clues",
        },
    )
    block, _ = markers(data)

    length_counts = count_fill_lengths(data["puzzle"], block)

    if not length_counts:
        print("No fills were found in the puzzle grid.")
    else:
        sorted_lengths = sorted(length_counts.items(), key=lambda x: (-x[1], x[0]))
        print_bar_chart(
            ((f"Length {length:2}", count) for length, count in sorted_lengths),
            rule_width=55,
        )

    short_entries = find_short_entries(data["puzzle"], block)

    if short_entries:
        plural = "entry" if len(short_entries) == 1 else "entries"
        print(f"✗ Found {len(short_entries)} {plural} shorter than 3 squares:")
        for direction, row, col in short_entries:
            print(f"‣ Row {row + 1}, Column {col + 1} ({direction})")
        print("-" * 55)

    across, down, total = count_clue_fills(data["clues"])

    print(f"Total: {total} ({across} Across, {down} Down)")

    grid_total = sum(length_counts.values())
    if grid_total != total:
        print(
            f"Warning: the grid contains {grid_total} entries but the file "
            f"lists {total} clue(s)."
        )
