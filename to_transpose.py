import argparse
import copy
import json
import os
import sys

from shared import make_is_playable


def load_ipuz(ipuz_file):
    """Loads and parses an ipuz file.

    Args:
        ipuz_file: Path to the .ipuz file to read.

    Returns:
        The parsed puzzle data as a dictionary.

    Raises:
        SystemExit: If the file cannot be found, cannot be parsed, or
            contains no puzzle grid.
    """
    try:
        with open(ipuz_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find the file '{ipuz_file}'")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: '{ipuz_file}' is not valid JSON ({exc}).")
        sys.exit(1)

    if not data.get("puzzle"):
        print("Error: No puzzle grid found in the file.")
        sys.exit(1)

    return data


def grid_dimensions(grid):
    """Returns the ``(rows, cols)`` dimensions of a 2-D grid.

    Args:
        grid: A 2-D list, whose rows may be ragged.

    Returns:
        A tuple ``(rows, cols)`` where ``cols`` is the width of the
        widest row.
    """
    rows = len(grid)
    cols = max(len(row) for row in grid) if rows > 0 else 0
    return rows, cols


def transpose_grid(grid, rows, cols):
    """Reflects a 2-D grid across its main diagonal.

    The cell at ``(r, c)`` of the result is taken from ``(c, r)`` of the
    input, so a ``rows x cols`` grid becomes a ``cols x rows`` grid.

    Args:
        grid: The 2-D list to transpose.
        rows: Number of rows in the input grid.
        cols: Number of columns in the input grid.

    Returns:
        A new 2-D list holding the transposed grid.
    """
    transposed = []
    for r in range(cols):
        row = []
        for c in range(rows):
            try:
                row.append(grid[c][r])
            except IndexError:
                row.append(None)
        transposed.append(row)
    return transposed


def clue_number(clue):
    """Extracts the entry number from an ipuz clue in any common format.

    Args:
        clue: A clue in ipuz form: a ``[number, text]`` pair, a mapping
            with a ``"number"`` key, or a bare string.

    Returns:
        The clue number as a string, or None if no number is present.
    """
    if isinstance(clue, dict):
        number = clue.get("number")
        return None if number is None else str(number)
    if isinstance(clue, (list, tuple)) and len(clue) >= 1:
        return str(clue[0])
    return None


def clue_text(clue):
    """Extracts the clue text from an ipuz clue in any common format.

    Args:
        clue: A clue in ipuz form: a ``[number, text]`` pair, a mapping
            with a ``"clue"`` key, or a bare string.

    Returns:
        The clue text as a string.
    """
    if isinstance(clue, dict):
        return clue.get("clue", "")
    if isinstance(clue, (list, tuple)) and len(clue) >= 2:
        return clue[1]
    return str(clue)


def rebuild_clue(template, number, text):
    """Rebuilds a clue in the same format as a template clue.

    Args:
        template: An existing clue whose format should be matched, or
            None to default to the mapping format.
        number: The entry number for the rebuilt clue.
        text: The clue text for the rebuilt clue.

    Returns:
        A clue in the same shape as ``template``.
    """
    if isinstance(template, (list, tuple)):
        return [number, text]
    return {"number": number, "clue": text}


def extract_entries(puzzle):
    """Finds every Across and Down entry in a puzzle grid.

    Walks the grid in reading order applying standard crossword
    numbering, and records the cells belonging to each entry.

    Args:
        puzzle: A 2-D list representing the crossword grid.

    Returns:
        A list of dictionaries, each with keys ``"direction"``,
        ``"number"``, and ``"cells"``, where ``"cells"`` is the ordered
        list of ``(row, col)`` coordinates the entry occupies.
    """
    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)

    entries = []
    number = 0

    for r in range(rows):
        for c in range(cols):
            if not is_playable(r, c):
                continue

            starts_across = not is_playable(r, c - 1) and is_playable(r, c + 1)
            starts_down = not is_playable(r - 1, c) and is_playable(r + 1, c)

            if starts_across or starts_down:
                number += 1

            if starts_across:
                cells = []
                cc = c
                while is_playable(r, cc):
                    cells.append((r, cc))
                    cc += 1
                entries.append(
                    {"direction": "Across", "number": number, "cells": cells}
                )

            if starts_down:
                cells = []
                rr = r
                while is_playable(rr, c):
                    cells.append((rr, c))
                    rr += 1
                entries.append({"direction": "Down", "number": number, "cells": cells})

    return entries


def build_clue_lookup(data, entries):
    """Indexes a puzzle's clues by the cells their entries occupy.

    Keying on cells rather than on clue numbers lets each clue follow
    its entry through the transpose, which renumbers the grid.

    Args:
        data: The parsed ipuz data.
        entries: The entry list produced by :func:`extract_entries` for
            the puzzle's grid.

    Returns:
        A tuple ``(lookup, template)`` where ``lookup`` maps a sorted
        tuple of cell coordinates to its clue text, and ``template`` is
        a sample clue used to preserve the file's clue format.
    """
    clues = data.get("clues", {}) or {}

    by_key = {}
    template = None
    for direction in ("Across", "Down"):
        for clue in clues.get(direction, []):
            if template is None:
                template = clue
            by_key[(direction, clue_number(clue))] = clue_text(clue)

    lookup = {}
    for entry in entries:
        key = (entry["direction"], str(entry["number"]))
        if key in by_key:
            lookup[tuple(sorted(entry["cells"]))] = by_key[key]

    return lookup, template


def renumber(data, clue_lookup, template):
    """Recomputes clue numbers and remaps clues for the transposed grid.

    Each entry of the transposed grid is matched back to the original
    entry occupying the same cells (with coordinates swapped), so clues
    follow their answers. Because the transpose preserves the reading
    order of every entry, an Across clue simply becomes a Down clue and
    vice versa, and no answer is reversed.

    Args:
        data: The parsed ipuz data for the transposed puzzle. Its
            ``"puzzle"`` grid is modified in place to carry the new
            numbering, and its ``"clues"`` are replaced.
        clue_lookup: The cell-keyed clue index built from the original
            grid by :func:`build_clue_lookup`.
        template: A sample clue used to preserve the clue format.

    Returns:
        The number of entries in the transposed grid.
    """
    puzzle = data["puzzle"]
    empty = data.get("empty", 0)
    entries = extract_entries(puzzle)

    # Blank the old numbering, then stamp the recomputed numbers in.
    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)
    for r in range(rows):
        for c in range(cols):
            if is_playable(r, c):
                puzzle[r][c] = empty

    new_clues = {"Across": [], "Down": []}

    for entry in entries:
        r, c = entry["cells"][0]
        puzzle[r][c] = entry["number"]

        # Undo the transpose to find where these cells came from.
        origins = [(cc, rr) for rr, cc in entry["cells"]]
        key = tuple(sorted(origins))
        if key not in clue_lookup:
            continue

        new_clues[entry["direction"]].append(
            rebuild_clue(template, entry["number"], clue_lookup[key])
        )

    if data.get("clues"):
        data["clues"] = new_clues

    return len(entries)


def to_transpose(ipuz_file, out_file):
    """Writes the transpose of an ipuz crossword to a new file.

    Reflects the grid across its main diagonal, which turns every Across
    entry into a Down entry and vice versa while leaving each answer
    reading forwards. The grid is renumbered and the clues are carried
    across to the entries they belong to, so the result is a fully valid
    crossword with the same fill as the original.

    Args:
        ipuz_file: Path to the .ipuz file to transpose.
        out_file: Path to write the transposed .ipuz file to.

    Returns:
        A tuple ``(width, height, entry_count)`` describing the
        transposed puzzle.

    Raises:
        SystemExit: If the input cannot be read or contains no grid.
    """
    data = load_ipuz(ipuz_file)
    rows, cols = grid_dimensions(data["puzzle"])

    clue_lookup, template = build_clue_lookup(data, extract_entries(data["puzzle"]))

    transposed = copy.deepcopy(data)
    for key in ("puzzle", "solution", "saved"):
        if transposed.get(key):
            transposed[key] = transpose_grid(transposed[key], rows, cols)

    if transposed.get("dimensions"):
        transposed["dimensions"] = {"width": rows, "height": cols}

    entry_count = renumber(transposed, clue_lookup, template)

    if isinstance(transposed.get("title"), str):
        transposed["title"] = f"{transposed['title']} [Transpose]"

    directory = os.path.dirname(out_file)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(transposed, f)

    return rows, cols, entry_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Write the transpose of an ipuz crossword: the grid reflected across its main diagonal, which swaps Across and Down entries while leaving every answer reading forwards."
    )
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")
    parser.add_argument(
        "--out",
        default=None,
        help="Path to write the transposed .ipuz file to (default: <name>_transpose.ipuz).",
    )

    args = parser.parse_args()

    out_file = args.out
    if out_file is None:
        stem = os.path.splitext(os.path.basename(args.ipuz_file))[0]
        out_file = f"{stem}_transpose.ipuz"

    print(f"Wrote {out_file}")
