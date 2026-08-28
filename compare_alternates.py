import argparse
import sys

from shared import (
    extract_entries,
    grid_dimensions,
    letter_at,
    load_ipuz,
    make_is_playable,
)


def compare_squares(puzzle_a, solution_a, puzzle_b, solution_b):
    """Counts how many white squares hold the same letter in two grids.

    Compares two crosswords that are alternate fills of one another
    (i.e., they share an identical layout of black and white squares)
    by checking the solution letter in every white square, reporting how
    much of the fill the two puzzles have in common.

    Args:
        puzzle_a: The crossword grid of the first puzzle.
        solution_a: The solution grid of the first puzzle.
        puzzle_b: The crossword grid of the second puzzle.
        solution_b: The solution grid of the second puzzle.

    Returns:
        A tuple ``(matching, total_white, percentage)`` where ``matching``
        is the number of white squares holding the same letter in both grids,
        ``total_white`` is the total number of white squares, and ``percentage``
        is ``matching`` expressed as a float percentage (0-100) of ``total_white``.

    Raises:
        SystemExit: If the two grids have different dimensions or
            different black square placements (in which case they are
            not alternate fills of each other), or if the shared grid
            has no white squares.
    """
    rows_a, cols_a = grid_dimensions(puzzle_a)
    rows_b, cols_b = grid_dimensions(puzzle_b)

    if (rows_a, cols_a) != (rows_b, cols_b):
        print(
            "Error: The two puzzles have different dimensions "
            f"({cols_a}x{rows_a} vs {cols_b}x{rows_b})."
        )
        print("Alternate fills must share an identical layout.")
        sys.exit(1)

    is_playable_a = make_is_playable(puzzle_a)
    is_playable_b = make_is_playable(puzzle_b)

    layout_mismatches = [
        (r + 1, c + 1)
        for r in range(rows_a)
        for c in range(cols_a)
        if is_playable_a(r, c) != is_playable_b(r, c)
    ]

    if layout_mismatches:
        print(
            f"Error: The two grids differ in black square placement at "
            f"{len(layout_mismatches)} square(s):"
        )
        for r, c in layout_mismatches[:10]:
            print(f"‣ Row {r}, Column {c}")
        if len(layout_mismatches) > 10:
            print(f"... and {len(layout_mismatches) - 10} more.")
        print("Alternate fills must share an identical layout.")
        sys.exit(1)

    total_white = 0
    matching = 0

    for r in range(rows_a):
        for c in range(cols_a):
            if not is_playable_a(r, c):
                continue

            total_white += 1
            letter_a = letter_at(solution_a, r, c)
            letter_b = letter_at(solution_b, r, c)

            if letter_a == letter_b:
                matching += 1

    if total_white == 0:
        print("Error: The grid has no playable white squares.")
        sys.exit(1)

    percentage = (matching / total_white) * 100

    return matching, total_white, percentage


def entry_word(solution, cells):
    """Reads the word an entry spells out in a solution grid.

    Args:
        solution: A 2-D list representing the solution grid.
        cells: The ordered list of ``(row, col)`` coordinates the entry
            occupies.

    Returns:
        The entry's letters joined into a single uppercase string.
    """
    return "".join(letter_at(solution, r, c) for r, c in cells)


def compare_entries(puzzle, solution_a, solution_b):
    """Compares the fill of two grids entry by entry.

    Because the two puzzles share an identical layout, the entries of
    either one describe both, so numbering and cell coordinates are
    taken from ``puzzle`` and the letters are read from each solution
    in turn.

    Args:
        puzzle: The crossword grid shared by both puzzles.
        solution_a: The solution grid of the first puzzle.
        solution_b: The solution grid of the second puzzle.

    Returns:
        A tuple ``(changed, total, unchanged)`` where ``changed`` is the
        number of entries spelling a different word in the two grids,
        ``total`` is the number of entries, and ``unchanged`` is a list
        of ``(direction, number, word)`` tuples for the entries whose
        word is common to both grids, in grid order.
    """
    entries = extract_entries(puzzle)

    changed = 0
    unchanged = []

    for entry in entries:
        word_a = entry_word(solution_a, entry["cells"])
        word_b = entry_word(solution_b, entry["cells"])

        if word_a == word_b:
            unchanged.append((entry["direction"], entry["number"], word_a))
        else:
            changed += 1

    return changed, len(entries), unchanged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare two ipuz crosswords that are alternate fills of each other, "
        "reporting how much of the fill they share by square and by entry."
    )
    parser.add_argument("ipuz_file_a", help="Path to the first .ipuz file to read.")
    parser.add_argument("ipuz_file_b", help="Path to the second .ipuz file to read.")
    parser.add_argument(
        "--show-unchanged",
        action="store_true",
        help="List the entries that spell the same word in both puzzles.",
    )

    args = parser.parse_args()

    required = ("puzzle", "solution")
    data_a = load_ipuz(args.ipuz_file_a, require=required)
    data_b = load_ipuz(args.ipuz_file_b, require=required)

    same_count, white_count, percent = compare_squares(
        data_a["puzzle"], data_a["solution"], data_b["puzzle"], data_b["solution"]
    )

    print(f"Total white squares:  {white_count}")
    print(f"Unchanged:            {same_count}")
    print(f"Different:            {white_count - same_count}")
    print(f"Overlap:              {percent:.2f}%")

    if same_count == white_count:
        print("✗ The two grids are identical.")

    changed_count, total_entries, unchanged = compare_entries(
        data_a["puzzle"], data_a["solution"], data_b["solution"]
    )

    print()
    print(f"Total entries:        {total_entries}")
    print(f"Unchanged:            {total_entries - changed_count}")
    print(f"Different:            {changed_count}")

    if args.show_unchanged and unchanged:
        print("\nUnchanged entries:")
        for direction, number, word in unchanged:
            print(f"‣ {number}-{direction}: {word}")

    if changed_count == total_entries:
        print("✓ Every entry is different! A fully disjoint alternate fill.")
