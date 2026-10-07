import argparse
import copy
import json
import os
import re

from shared import (
    BARS,
    CLUE_CELLS,
    CLUE_LABELS,
    CLUE_LINKS,
    CUSTOM_LABELS,
    MULTI_ENTRY_CLUES,
    ORIENTED_STYLES,
    OTHER_DIRECTIONS,
    UNNUMBERED_CLUES,
    clue_group,
    clue_number,
    clue_text,
    extract_entries,
    grid_dimensions,
    load_ipuz,
    make_is_playable,
    markers,
    print_warning,
    rebuild_clue,
)

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

TRANSPOSED_DIRECTION = {
    **OPPOSITE,
    "Diagonal": "Diagonal",
    "Diagonal Up": "Diagonal Down Left",
    "Diagonal Down Left": "Diagonal Up",
    "Diagonal Up Left": "Diagonal Up Left",
}


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


def transpose_value(value):
    """Swaps the directions named inside a solution cell.

    A cell of an ipuz solution may give a different value for each
    direction, as in ``{"Across": "Q", "Down": "Z"}``. Transposing the
    grid turns Across into Down, so those keys must swap with it.

    Args:
        value: A single cell drawn from an ipuz solution grid.

    Returns:
        The cell with every direction replaced by the direction it
        becomes in the transposed grid.
    """
    if isinstance(value, list):
        return [transpose_value(item) for item in value]

    if isinstance(value, dict):
        return {
            TRANSPOSED_DIRECTION.get(key, key): (
                item if key == "style" else transpose_value(item)
            )
            for key, item in value.items()
        }

    return value


def transpose_zone(zone):
    """Reflects an ipuz zone across the grid's main diagonal.

    A zone names its cells by ``[column, row]`` coordinates, given as a
    bounding rectangle, a line, or an explicit list of cells, so each
    pair is swapped.

    Args:
        zone: A single entry of an ipuz ``"zones"`` list.

    Returns:
        A copy of the zone covering the same squares in the transposed
        grid.
    """
    if not isinstance(zone, dict):
        return zone

    zone = dict(zone)

    rect = zone.get("rect")
    if isinstance(rect, list) and len(rect) == 4:
        col1, row1, col2, row2 = rect
        zone["rect"] = [row1, col1, row2, col2]

    line = zone.get("line")
    if isinstance(line, list) and len(line) == 3:
        start, step, length = line
        zone["line"] = [list(reversed(start)), list(reversed(step)), length]

    cells = zone.get("cells")
    if isinstance(cells, list):
        zone["cells"] = [list(reversed(cell)) for cell in cells]

    return zone


def set_label(puzzle, r, c, label):
    """Relabels a puzzle grid cell, keeping any styling it carries.

    Args:
        puzzle: The 2-D puzzle grid, which is modified in place.
        r: Zero-indexed row coordinate.
        c: Zero-indexed column coordinate.
        label: The cell's new label: an entry number, or the file's
            ``"empty"`` marker for an unnumbered square.

    Returns:
        None
    """
    cell = puzzle[r][c]
    if isinstance(cell, dict):
        cell["cell"] = label
    else:
        puzzle[r][c] = label


def remove_stale_fields(data, changed):
    """Removes fields that transposing the puzzle has made invalid.

    The checksum is a hash of the solution read row by row, which no
    longer holds once the rows have become columns. Extension fields
    (those with a colon in their name) are removed as the ipuz
    specification directs: each is dropped unless the file's
    ``"volatile"`` field says it survives the changes made.

    Args:
        data: The parsed ipuz data for the transposed puzzle, which is
            modified in place.
        changed: The set of top-level fields the transpose has altered.

    Returns:
        A list of the names of the fields removed.
    """
    removed = []

    if "checksum" in data:
        del data["checksum"]
        removed.append("checksum")

    volatile = data.get("volatile")
    if not isinstance(volatile, dict):
        volatile = {}

    for field in list(data):
        if ":" not in field:
            continue

        namespace = field.split(":", 1)[0]
        volatility = volatile.get(field, volatile.get(namespace, "*"))
        if not isinstance(volatility, str) or volatility == "":
            continue

        triggers = {name.strip() for name in volatility.split(",")}
        if volatility == "*" or triggers & changed:
            del data[field]
            removed.append(field)

    return removed


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


def build_renumber_map(original_entries, transposed_entries):
    """Maps each original entry to its counterpart in the transposed grid.

    Args:
        original_entries: Entries of the original grid.
        transposed_entries: Entries of the transposed grid.

    Returns:
        A dictionary mapping ``(direction, label)`` in the original
        grid, where ``label`` is the entry's label as a string, to
        ``(direction, number)`` in the transposed grid.
    """
    by_cells = {tuple(sorted(entry["cells"])): entry for entry in transposed_entries}

    mapping = {}
    for entry in original_entries:
        key = tuple(sorted((c, r) for r, c in entry["cells"]))
        target = by_cells.get(key)
        if target is not None:
            mapping[(entry["direction"], entry["label"])] = (
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
        targets = [mapping.get((canonical, n)) for n in numbers]

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


def renumber(data, clue_lookup, mapping, sort_references=False):
    """Recomputes clue numbers and remaps clues for the transposed grid.

    Each entry of the transposed grid is matched back to the original
    entry occupying the same cells (with coordinates swapped), so clues
    follow their solutions. Because the transpose preserves the reading
    order of every entry, an Across clue simply becomes a Down clue and
    vice versa, and no solution is reversed. Cross-references inside the
    clue text are rewritten to match the new numbering. Each clue keeps
    its own format, and the clue lists keep whatever headings the file
    gives them, such as ``"Across:Horizontales"``.

    Args:
        data: The parsed ipuz data for the transposed puzzle. Its
            ``"puzzle"`` grid is modified in place to carry the new
            numbering, and its ``"clues"`` are replaced.
        clue_lookup: The cell-keyed clue index built from the original
            grid by :func:`build_clue_lookup`.
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
    block, _ = markers(data)
    empty = data["empty"] if data.get("empty") is not None else 0
    entries = extract_entries(puzzle, block)

    is_playable = make_is_playable(puzzle, block)
    rows, cols = grid_dimensions(puzzle)
    for r in range(rows):
        for c in range(cols):
            if is_playable(r, c):
                set_label(puzzle, r, c, empty)

    group_keys = {
        direction: clue_group(data.get("clues"), direction)[0]
        for direction in ("Across", "Down")
    }
    new_clues = {key: [] for key in data.get("clues") or {}}
    for key in group_keys.values():
        new_clues.setdefault(key, [])

    rewritten = 0
    unresolved = 0

    for entry in entries:
        r, c = entry["cells"][0]
        set_label(puzzle, r, c, entry["number"])

        key = tuple(sorted((cc, rr) for rr, cc in entry["cells"]))
        if key not in clue_lookup:
            continue

        original = clue_lookup[key]
        text, changed, missing = rewrite_references(
            clue_text(original), mapping, sort_references
        )
        rewritten += changed
        unresolved += missing

        new_clues[group_keys[entry["direction"]]].append(
            rebuild_clue(original, entry["number"], text)
        )

    if data.get("clues"):
        data["clues"] = new_clues

    return rewritten, unresolved


def build_clue_lookup(data, entries):
    """Indexes a puzzle's clues by the cells their entries occupy.

    Keying on cells rather than on clue numbers lets each clue follow
    its entry through the transpose, which renumbers the grid. A clue
    belongs to the entry whose first cell carries the clue's number as
    its label, so grids labelled in some other way than standard
    numbering are matched correctly too.

    Args:
        data: The parsed ipuz data.
        entries: The entry list produced by :func:`extract_entries` for
            the puzzle's grid.

    Returns:
        A tuple ``(lookup, unmatched)`` where ``lookup`` maps a sorted
        tuple of cell coordinates to its clue, and ``unmatched`` is the
        number of Across and Down clues that belong to no entry.
    """
    clues = data.get("clues", {}) or {}

    by_key = {}
    total = 0
    for direction in ("Across", "Down"):
        for clue in clue_group(clues, direction)[1]:
            total += 1
            by_key[(direction, clue_number(clue))] = clue

    lookup = {}
    for entry in entries:
        key = (entry["direction"], entry["label"])
        if key in by_key:
            lookup[tuple(sorted(entry["cells"]))] = by_key[key]

    return lookup, total - len(lookup)


def to_transpose(ipuz_file, out_file, sort_references=False):
    """Writes the transpose of an ipuz crossword to a new file.

    Reflects the grid across its main diagonal, which turns every Across
    entry into a Down entry and vice versa while leaving each answer
    reading forwards. The grid is renumbered, the clues are carried
    across to the entries they belong to, and any cross-references in
    the clue text are updated to the new numbers and directions, so the
    result is a fully valid crossword with the same fill as the original.

    Cell styles, zones, and direction-specific solution values are
    carried across too. A puzzle is refused if it relies on something
    that cannot be carried across, such as bars between cells, and a
    warning is printed for anything that has to be changed or removed.

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
        SystemExit: If the input cannot be read, contains no grid, or
            uses a feature that cannot be transposed.
    """
    data = load_ipuz(
        ipuz_file,
        require=("puzzle",),
        reject=(
            BARS,
            OTHER_DIRECTIONS,
            UNNUMBERED_CLUES,
            MULTI_ENTRY_CLUES,
            CLUE_CELLS,
        ),
        warn={
            CUSTOM_LABELS: "replaced by standard numbering",
            CLUE_LABELS: "removed, since the entries are renumbered",
            CLUE_LINKS: "removed, since the entries are renumbered",
            ORIENTED_STYLES: "kept as they are, so they may need adjusting",
        },
    )
    block, empty = markers(data)
    rows, cols = grid_dimensions(data["puzzle"])

    original_entries = extract_entries(data["puzzle"], block, empty)
    clue_lookup, unmatched = build_clue_lookup(data, original_entries)

    if unmatched:
        print_warning(
            f"{unmatched} clue(s) in '{ipuz_file}' belong to no entry in "
            "the grid and were left out."
        )

    transposed = copy.deepcopy(data)
    changed = {"dimensions"}
    for key in ("puzzle", "solution", "saved"):
        if transposed.get(key):
            transposed[key] = transpose_grid(transposed[key], rows, cols)
            changed.add(key)

    for key in ("solution", "saved"):
        if transposed.get(key):
            transposed[key] = [
                [transpose_value(cell) for cell in row] for row in transposed[key]
            ]

    if transposed.get("zones"):
        transposed["zones"] = [transpose_zone(zone) for zone in transposed["zones"]]
        changed.add("zones")

    if transposed.get("dimensions"):
        transposed["dimensions"] = {"width": rows, "height": cols}

    mapping = build_renumber_map(
        original_entries, extract_entries(transposed["puzzle"], block)
    )

    rewritten, unresolved = renumber(transposed, clue_lookup, mapping, sort_references)

    if transposed.get("clues"):
        changed.add("clues")

    if isinstance(transposed.get("title"), str):
        transposed["title"] = f"{transposed['title']} [Transpose]"
        changed.add("title")

    removed = remove_stale_fields(transposed, changed)
    if removed:
        print_warning(
            f"left out fields of '{ipuz_file}' that transposing makes "
            f"invalid: {', '.join(removed)}."
        )

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
