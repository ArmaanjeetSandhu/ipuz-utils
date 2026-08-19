import argparse
import copy
import json
import os
import re
import sys

from shared import make_is_playable

_SEPARATOR = r"(?:\s*,\s*(?:(?:and|or|&)\s+)?|\s+(?:and|or|&)\s+)"

REFERENCE_RUN = re.compile(
    r"(?<![\w-])"
    r"((?:\d+\s*-" + _SEPARATOR + r")*)"
    r"(\d+)"
    r"(\s*-?\s*)"
    r"(Across|Down)\b",
    re.IGNORECASE,
)


OPPOSITE = {"Across": "Down", "Down": "Across"}


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


def match_case(word, model):
    """Renders a word using the capitalisation style of a model string.

    Args:
        word: The word to restyle, given in title case.
        model: The string whose capitalisation should be imitated.

    Returns:
        ``word`` in upper case, lower case, or title case, following
        the style of ``model``.
    """
    if model.isupper():
        return word.upper()
    if model.islower():
        return word.lower()
    return word


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


def build_renumber_map(original_entries, transposed_entries):
    """Maps each original entry to its counterpart in the transposed grid.

    Args:
        original_entries: Entries of the original grid.
        transposed_entries: Entries of the transposed grid.

    Returns:
        A dictionary mapping ``(direction, number)`` in the original
        grid to ``(direction, number)`` in the transposed grid.
    """
    by_cells = {tuple(sorted(entry["cells"])): entry for entry in transposed_entries}

    mapping = {}
    for entry in original_entries:
        key = tuple(sorted((c, r) for r, c in entry["cells"]))
        target = by_cells.get(key)
        if target is not None:
            mapping[(entry["direction"], entry["number"])] = (
                target["direction"],
                target["number"],
            )

    return mapping


def rewrite_references(text, mapping, sort_references=False):
    """Updates cross-references in a clue to suit the transposed grid.

    Transposing renumbers the grid and turns every Across entry into a
    Down entry and vice versa, so a clue reading "See 37-Across" must be
    rewritten to name the new number and direction of that same entry.
    Runs of references that share one direction word, such as
    "17-, 27-, 39- and 47-Down", are rewritten as a whole.

    A run is left untouched if any entry it names cannot be resolved, so
    that a typo or a reference to a nonexistent clue is preserved rather
    than silently mangled.

    Args:
        text: The clue text to rewrite.
        mapping: The ``(direction, number)`` map from
            :func:`build_renumber_map`.
        sort_references: If True, list the rewritten numbers in
            ascending order rather than keeping their original order.

    Returns:
        A tuple ``(new_text, rewritten, unresolved)`` where ``rewritten``
        counts the reference runs that were updated and ``unresolved``
        counts those left untouched because an entry could not be found.
    """
    counts = {"rewritten": 0, "unresolved": 0}

    def replace(match):
        leading, final = match.group(1), match.group(2)
        separator, direction = match.group(3), match.group(4)
        canonical = "Across" if direction.lower() == "across" else "Down"

        numbers = re.findall(r"\d+", leading) + [final]
        targets = [mapping.get((canonical, int(n))) for n in numbers]

        if any(t is None for t in targets):
            counts["unresolved"] += 1
            return match.group(0)

        new_numbers = [number for _, number in targets]
        if sort_references:
            new_numbers.sort()

        new_direction = match_case(OPPOSITE[canonical], direction)

        leading_numbers = iter(new_numbers[:-1])
        new_leading = re.sub(r"\d+", lambda _: str(next(leading_numbers)), leading)

        counts["rewritten"] += 1
        return f"{new_leading}{new_numbers[-1]}{separator}{new_direction}"

    return (REFERENCE_RUN.sub(replace, text), counts["rewritten"], counts["unresolved"])


def renumber(data, clue_lookup, template, mapping, sort_references=False):
    """Recomputes clue numbers and remaps clues for the transposed grid.

    Each entry of the transposed grid is matched back to the original
    entry occupying the same cells (with coordinates swapped), so clues
    follow their answers. Because the transpose preserves the reading
    order of every entry, an Across clue simply becomes a Down clue and
    vice versa, and no answer is reversed. Cross-references inside the
    clue text are rewritten to match the new numbering.

    Args:
        data: The parsed ipuz data for the transposed puzzle. Its
            ``"puzzle"`` grid is modified in place to carry the new
            numbering, and its ``"clues"`` are replaced.
        clue_lookup: The cell-keyed clue index built from the original
            grid by :func:`build_clue_lookup`.
        template: A sample clue used to preserve the clue format.
        mapping: The ``(direction, number)`` map from
            :func:`build_renumber_map`.
        sort_references: If True, list rewritten reference numbers in
            ascending order.

    Returns:
        A tuple ``(rewritten, unresolved)`` counting the cross-reference
        runs that were updated and those left untouched because an entry
        could not be found.
    """
    puzzle = data["puzzle"]
    empty = data.get("empty", 0)
    entries = extract_entries(puzzle)

    is_playable = make_is_playable(puzzle)
    rows, cols = grid_dimensions(puzzle)
    for r in range(rows):
        for c in range(cols):
            if is_playable(r, c):
                puzzle[r][c] = empty

    new_clues = {"Across": [], "Down": []}
    rewritten = 0
    unresolved = 0

    for entry in entries:
        r, c = entry["cells"][0]
        puzzle[r][c] = entry["number"]

        key = tuple(sorted((cc, rr) for rr, cc in entry["cells"]))
        if key not in clue_lookup:
            continue

        text, changed, missing = rewrite_references(
            clue_lookup[key], mapping, sort_references
        )
        rewritten += changed
        unresolved += missing

        new_clues[entry["direction"]].append(
            rebuild_clue(template, entry["number"], text)
        )

    if data.get("clues"):
        data["clues"] = new_clues

    return rewritten, unresolved


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


def to_transpose(ipuz_file, out_file, sort_references=False):
    """Writes the transpose of an ipuz crossword to a new file.

    Reflects the grid across its main diagonal, which turns every Across
    entry into a Down entry and vice versa while leaving each answer
    reading forwards. The grid is renumbered, the clues are carried
    across to the entries they belong to, and any cross-references in
    the clue text are updated to the new numbers and directions, so the
    result is a fully valid crossword with the same fill as the original.

    Args:
        ipuz_file: Path to the .ipuz file to transpose.
        out_file: Path to write the transposed .ipuz file to.
        sort_references: If True, list rewritten reference numbers in
            ascending order rather than keeping their original order.

    Returns:
        A tuple ``(rewritten, unresolved)`` counting the cross-reference
        runs that were updated and those left untouched because an entry
        could not be found.

    Raises:
        SystemExit: If the input cannot be read or contains no grid.
    """
    data = load_ipuz(ipuz_file)
    rows, cols = grid_dimensions(data["puzzle"])

    original_entries = extract_entries(data["puzzle"])
    clue_lookup, template = build_clue_lookup(data, original_entries)

    transposed = copy.deepcopy(data)
    for key in ("puzzle", "solution", "saved"):
        if transposed.get(key):
            transposed[key] = transpose_grid(transposed[key], rows, cols)

    if transposed.get("dimensions"):
        transposed["dimensions"] = {"width": rows, "height": cols}

    mapping = build_renumber_map(
        original_entries, extract_entries(transposed["puzzle"])
    )

    rewritten, unresolved = renumber(
        transposed, clue_lookup, template, mapping, sort_references
    )

    if isinstance(transposed.get("title"), str):
        transposed["title"] = f"{transposed['title']} [Transpose]"

    directory = os.path.dirname(out_file)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(transposed, f)

    return rewritten, unresolved


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
    parser.add_argument(
        "--sort-references",
        action="store_true",
        help="List rewritten cross-reference numbers in ascending order instead of keeping their original order.",
    )

    args = parser.parse_args()

    out_file = args.out
    if out_file is None:
        stem = os.path.splitext(os.path.basename(args.ipuz_file))[0]
        out_file = f"{stem}_transpose.ipuz"

    rewritten, unresolved = to_transpose(args.ipuz_file, out_file, args.sort_references)

    print(f"Cross-references: {rewritten} rewritten")
    if unresolved:
        print(f"                  {unresolved} left unchanged (entry not found)")
    print(f"Wrote {out_file}")
