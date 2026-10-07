"""Shared utilities for reading and analysing ipuz crossword files."""

import argparse
import html
import json
import re
import sys

BLOCK = "#"
EMPTY = "0"

CROSSWORD_KIND = "http://ipuz.org/crossword"
SUPPORTED_KINDS = (CROSSWORD_KIND, CROSSWORD_KIND + "/crypticcrossword")
SUPPORTED_VERSIONS = (1, 2)

DIRECTIONS = (
    "Across",
    "Down",
    "Diagonal",
    "Diagonal Up",
    "Diagonal Down Left",
    "Diagonal Up Left",
    "Zones",
    "Clues",
)

BARS = "bars"
ORIENTED_STYLES = "oriented_styles"
STYLES = "styles"
GIVENS = "givens"
ZONES = "zones"
MULTI_VALUES = "multi_values"
OTHER_DIRECTIONS = "other_directions"
UNNUMBERED_CLUES = "unnumbered_clues"
MULTI_ENTRY_CLUES = "multi_entry_clues"
CLUE_CELLS = "clue_cells"
CLUE_LABELS = "clue_labels"
CLUE_LINKS = "clue_links"
CLUE_FIELDS = "clue_fields"
CUSTOM_LABELS = "custom_labels"
FORMATTING = "formatting"

_FEATURE_DESCRIPTIONS = {
    BARS: "bars between cells",
    ORIENTED_STYLES: "cell styles that depend on the grid's orientation",
    STYLES: "cell styles",
    GIVENS: "prefilled cell values",
    ZONES: "zones",
    MULTI_VALUES: "solution cells holding several or direction-specific values",
    OTHER_DIRECTIONS: "clue lists other than Across and Down",
    UNNUMBERED_CLUES: "unnumbered clues",
    MULTI_ENTRY_CLUES: "clues shared by several entries",
    CLUE_CELLS: "clues that list their own cells",
    CLUE_LABELS: "clue labels shown in place of clue numbers",
    CLUE_LINKS: "links between clues",
    CLUE_FIELDS: "extra clue fields",
    CUSTOM_LABELS: "cell labels that differ from standard numbering",
    FORMATTING: "HTML formatting in text",
}

_BAR_STYLE_KEYS = {"barred", "dotted", "dashed"}
_ORIENTED_STYLE_KEYS = {
    "divided",
    "mark",
    "lessthan",
    "greaterthan",
    "equal",
    "image",
    "imagebg",
    "slice",
}
_CLUE_LINK_KEYS = {"references", "continued", "location"}
_PLAIN_CLUE_KEYS = {"number", "numbers", "cells", "label", "clue"}

_LINE_BREAK = re.compile(r"<br[ \r\n\t]*/?>", re.IGNORECASE)
_FORMAT_TAG = re.compile(r"</?(?:b|i|s|u|em|strong|big|small|sup|sub)>", re.IGNORECASE)

_MISSING_MESSAGES = {
    "puzzle": "No puzzle grid found",
    "solution": "No solution grid found",
    "clues": "No clues found",
}


def print_warning(message):
    """Prints a warning to standard error, leaving standard output clean.

    Args:
        message: The text of the warning.

    Returns:
        None
    """
    print(f"Warning: {message}", file=sys.stderr)


def _fail(ipuz_file, reason):
    """Reports why a file cannot be used and exits.

    Args:
        ipuz_file: Path of the offending file.
        reason: The rest of the sentence that starts with the file name.

    Raises:
        SystemExit: Always.
    """
    print(f"Error: '{ipuz_file}' {reason}.")
    sys.exit(1)


def _is_grid(value):
    """Tells whether a value is a 2-D list, as every ipuz grid must be."""
    return isinstance(value, list) and all(isinstance(row, list) for row in value)


def _as_size(value):
    """Reads a grid size, which must be a whole number of at least one.

    ipuz treats a string holding just a number as that number, so
    ``"15"`` is accepted alongside ``15``.

    Args:
        value: The value given for a width or height.

    Returns:
        The size as an integer, or None if the value is not a valid size.
    """
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    return value if type(value) is int and value >= 1 else None


def _validate(data, ipuz_file):
    """Checks that parsed JSON is an ipuz crossword this code can read.

    Confirms the fields the ipuz specification makes mandatory for a
    crossword (``"version"``, ``"kind"``, ``"dimensions"`` and
    ``"puzzle"``) and the shape of the optional ones the tools rely on.
    Rows and columns left out of the ``"puzzle"`` grid are filled in
    with None, which is how ipuz marks an omitted cell, so that the grid
    always matches its stated dimensions.

    Args:
        data: The parsed contents of the file.
        ipuz_file: Path of the file, for error messages.

    Raises:
        SystemExit: If the file is not a valid ipuz crossword, or is a
            version or variant that is not supported.
    """
    invalid = "is not a valid ipuz crossword"

    if not isinstance(data, dict):
        _fail(ipuz_file, f"{invalid}: it does not hold a JSON object")

    version = data.get("version")
    match = (
        re.fullmatch(r"http://ipuz\.org/v(\d+)", version)
        if isinstance(version, str)
        else None
    )
    if not match:
        _fail(ipuz_file, f"{invalid}: the version field is missing or malformed")
    if int(match.group(1)) not in SUPPORTED_VERSIONS:
        _fail(
            ipuz_file,
            f"uses ipuz version {match.group(1)}, which this program does not support",
        )

    kinds = data.get("kind")
    if (
        not isinstance(kinds, list)
        or not kinds
        or not all(isinstance(kind, str) for kind in kinds)
    ):
        _fail(ipuz_file, f"{invalid}: the kind field is missing or malformed")

    is_crossword = False
    unrecognised = []
    for kind in kinds:
        name, _, kind_version = kind.partition("#")
        if name in SUPPORTED_KINDS:
            if kind_version not in ("", "1"):
                _fail(
                    ipuz_file,
                    f"uses version {kind_version} of the puzzle kind '{name}', "
                    "which this program does not support",
                )
            is_crossword = True
        elif name.startswith(CROSSWORD_KIND + "/"):
            _fail(
                ipuz_file,
                f"is a crossword variant this program does not support ({kind})",
            )
        else:
            unrecognised.append(kind)

    if not is_crossword:
        _fail(ipuz_file, f"is not a crossword (kind: {', '.join(kinds)})")
    if unrecognised:
        print_warning(
            f"'{ipuz_file}' also has the puzzle kind {', '.join(unrecognised)}, "
            "which this program does not recognise; it is read as a plain crossword."
        )

    for key in ("block", "empty"):
        value = data.get(key)
        allowed = (str,) if key == "block" else (str, int)
        if value is not None and (
            not isinstance(value, allowed) or isinstance(value, bool)
        ):
            _fail(ipuz_file, f"{invalid}: the {key} field is malformed")

    puzzle = data.get("puzzle")
    if not puzzle:
        print(f"Error: {_MISSING_MESSAGES['puzzle']} in '{ipuz_file}'.")
        sys.exit(1)

    for key in ("puzzle", "solution", "saved"):
        if data.get(key) is not None and not _is_grid(data[key]):
            _fail(ipuz_file, f"{invalid}: the {key} field is not a grid of rows")

    dimensions = data.get("dimensions")
    if not isinstance(dimensions, dict):
        dimensions = {}
    width = _as_size(dimensions.get("width"))
    height = _as_size(dimensions.get("height"))
    if width is None or height is None:
        _fail(ipuz_file, f"{invalid}: the dimensions field is missing or malformed")

    dimensions["width"], dimensions["height"] = width, height
    if len(puzzle) > height or any(len(row) > width for row in puzzle):
        _fail(ipuz_file, f"{invalid}: the puzzle grid is larger than its dimensions")

    for row in puzzle:
        row.extend([None] * (width - len(row)))
    puzzle.extend([None] * width for _ in range(height - len(puzzle)))

    clues = data.get("clues")
    if clues is not None:
        if not isinstance(clues, dict) or not all(
            isinstance(group, list) for group in clues.values()
        ):
            _fail(ipuz_file, f"{invalid}: the clues field is malformed")
        for key in clues:
            if split_direction(key)[0] not in DIRECTIONS:
                _fail(ipuz_file, f"{invalid}: '{key}' is not a clue direction")


def load_ipuz(ipuz_file, require=(), reject=(), warn=None, unused_fields=None):
    """Loads and parses an ipuz file, checking that it has what is needed.

    As the ipuz specification requires of a program that does not
    implement the whole format, the file is refused if it uses a feature
    the calling tool cannot handle, and a warning naming each feature
    the tool will ignore or lose is printed to standard error.

    Args:
        ipuz_file: Path to the .ipuz file to read.
        require: An iterable of top-level keys that must be present and
            non-empty, drawn from ``"puzzle"``, ``"solution"``, and
            ``"clues"``.
        reject: An iterable of feature constants from this module. The
            file is refused if it uses any of them.
        warn: A mapping from feature constants to a few words saying
            what becomes of that feature, such as ``"not drawn"``.
        unused_fields: A pair ``(fields, consequence)`` naming top-level
            ipuz fields the tool does not carry into its output and
            what becomes of them, or None.

    Returns:
        The parsed puzzle data as a dictionary.

    Raises:
        SystemExit: If the file cannot be found, is not valid JSON, is
            not an ipuz crossword, lacks one of the required keys, or
            uses a feature listed in ``reject``.
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

    _validate(data, ipuz_file)

    for key in require:
        if not data.get(key):
            print(f"Error: {_MISSING_MESSAGES[key]} in '{ipuz_file}'.")
            sys.exit(1)

    features = detect_features(data)

    refused = [feature for feature in reject if feature in features]
    if refused:
        print(f"Error: '{ipuz_file}' uses features this program does not support:")
        for feature in refused:
            print(f"‣ {describe_feature(feature, features[feature])}")
        sys.exit(1)

    notes = [
        f"{describe_feature(feature, features[feature])}: {consequence}"
        for feature, consequence in (warn or {}).items()
        if feature in features
    ]
    if unused_fields:
        fields, consequence = unused_fields
        present = [field for field in fields if data.get(field)]
        if present:
            notes.append(f"top-level fields ({', '.join(present)}): {consequence}")

    if notes:
        print_warning(
            f"'{ipuz_file}' uses features this program does not fully support:"
        )
        for note in notes:
            print(f"‣ {note}", file=sys.stderr)

    return data


def markers(data):
    """Reads the block and empty-cell markers an ipuz file uses.

    Args:
        data: The parsed ipuz data.

    Returns:
        A tuple ``(block, empty)`` holding the file's ``"block"`` and
        ``"empty"`` values, or the ipuz defaults of ``"#"`` and ``"0"``
        where the file does not set them.
    """
    block = data.get("block")
    empty = data.get("empty")
    return (
        BLOCK if block is None else block,
        EMPTY if empty is None else empty,
    )


def is_omitted(cell):
    """Determines whether a puzzle grid cell is omitted from the grid.

    Args:
        cell: A single cell drawn from an ipuz puzzle grid.

    Returns:
        True if the cell is null, or is a mapping whose ``"cell"`` is
        null; False otherwise.
    """
    if isinstance(cell, dict):
        return "cell" in cell and cell["cell"] is None
    return cell is None


def is_block(cell, block=BLOCK):
    """Determines whether a puzzle grid cell is a block (black square).

    Args:
        cell: A single cell drawn from an ipuz puzzle grid, either bare
            or a mapping carrying its content under a ``"cell"`` key.
        block: The file's ``"block"`` marker. Defaults to the ipuz
            default of ``"#"``.

    Returns:
        True if the cell is a block; False otherwise.
    """
    if isinstance(cell, dict):
        cell = cell.get("cell")
    return isinstance(cell, str) and cell == block


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


def make_is_playable(puzzle, block=BLOCK):
    """Returns an ``is_playable`` function bound to the given puzzle grid.

    The returned function determines whether a grid cell is a playable
    (white) square, i.e., within bounds, not omitted, and not a block.

    Args:
        puzzle: A 2-D list representing the crossword grid, as found
            in the ``"puzzle"`` key of an ipuz file.
        block: The file's ``"block"`` marker. Defaults to the ipuz
            default of ``"#"``.

    Returns:
        A callable ``is_playable(r, c) -> bool`` that accepts
        zero-indexed row and column coordinates.
    """
    rows, cols = grid_dimensions(puzzle)

    def is_playable(r, c):
        """Determines whether a grid cell is a playable (white) square.

        Args:
            r: Zero-indexed row coordinate.
            c: Zero-indexed column coordinate.

        Returns:
            True if the coordinate is within the grid bounds and the
            cell is neither omitted nor a block; False otherwise.
        """
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return False

        try:
            cell = puzzle[r][c]
        except IndexError:
            return False

        return not is_omitted(cell) and not is_block(cell, block)

    return is_playable


def extract_entries(puzzle, block=BLOCK, empty=EMPTY):
    """Finds every Across and Down entry in a puzzle grid.

    Walks the grid in reading order applying standard crossword
    numbering, and records the cells belonging to each entry.

    Args:
        puzzle: A 2-D list representing the crossword grid.
        block: The file's ``"block"`` marker.
        empty: The file's ``"empty"`` marker.

    Returns:
        A list of dictionaries, each with keys ``"direction"``,
        ``"number"``, ``"label"``, and ``"cells"``. ``"number"`` is the
        entry's number under standard numbering, ``"label"`` is the
        label the grid itself gives the entry's first cell (or the
        standard number as a string if that cell is unlabelled), and
        ``"cells"`` is the ordered list of ``(row, col)`` coordinates
        the entry occupies.
    """
    is_playable = make_is_playable(puzzle, block)
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

            label = cell_label(puzzle[r][c], empty, block) or str(number)

            if starts_across:
                cells = []
                cc = c
                while is_playable(r, cc):
                    cells.append((r, cc))
                    cc += 1
                entries.append(
                    {
                        "direction": "Across",
                        "number": number,
                        "label": label,
                        "cells": cells,
                    }
                )

            if starts_down:
                cells = []
                rr = r
                while is_playable(rr, c):
                    cells.append((rr, c))
                    rr += 1
                entries.append(
                    {
                        "direction": "Down",
                        "number": number,
                        "label": label,
                        "cells": cells,
                    }
                )

    return entries


def cell_value(cell, block=BLOCK, empty=EMPTY):
    """Unwraps the text held by a cell of an ipuz solution grid.

    A solution cell may be a bare string, the file's block or empty
    marker, or a mapping carrying the letter under a ``"value"`` key
    alongside styling information. Cells holding several values or a
    value per direction cannot be reduced to one string; tools that read
    solutions refuse such files through ``load_ipuz``.

    Args:
        cell: A single cell drawn from an ipuz solution grid.
        block: The file's ``"block"`` marker.
        empty: The file's ``"empty"`` marker.

    Returns:
        The cell's text as a string, or an empty string if the cell is
        omitted, empty, or a block.
    """
    if isinstance(cell, dict):
        cell = cell.get("value")

    if cell is None or (isinstance(cell, str) and cell == block):
        return ""

    if isinstance(cell, (str, int)) and str(cell) == str(empty):
        return ""

    return str(cell)


def cell_label(cell, empty=EMPTY, block=BLOCK):
    """Reads the number, if any, that a puzzle grid cell is labelled with.

    An ipuz puzzle cell holds either the value of the file's ``"empty"``
    key (meaning an unnumbered white square), a block, or the entry
    number the square starts, given as a number or a string. The cell
    may also be a mapping carrying that value under a ``"cell"`` key
    alongside styling information.

    Args:
        cell: A single cell drawn from an ipuz puzzle grid.
        empty: The file's ``"empty"`` marker, which labels an unnumbered
            white square. Defaults to the ipuz default of ``"0"``.
        block: The file's ``"block"`` marker. Defaults to the ipuz
            default of ``"#"``.

    Returns:
        The cell's label as a string, or an empty string if the cell is
        a block or carries no number.
    """
    if is_omitted(cell) or is_block(cell, block):
        return ""

    if isinstance(cell, dict):
        cell = cell.get("cell", empty)

    if str(cell) == str(empty):
        return ""

    return str(cell)


def letter_at(solution, r, c, block=BLOCK, empty=EMPTY):
    """Retrieves the uppercase solution letter at a grid cell.

    Args:
        solution: A 2-D list representing the solution grid.
        r: Zero-indexed row coordinate.
        c: Zero-indexed column coordinate.
        block: The file's ``"block"`` marker.
        empty: The file's ``"empty"`` marker.

    Returns:
        The uppercase letter occupying the cell, or an empty string if
        the cell is missing or empty.
    """
    try:
        cell = solution[r][c]
    except IndexError:
        return ""

    return cell_value(cell, block, empty).upper()


def split_direction(key):
    """Splits a key of the ipuz ``"clues"`` mapping into its two parts.

    A key is a direction such as ``"Across"``, optionally followed by a
    colon and the heading to show solvers instead, as in
    ``"Across:Horizontales"``.

    Args:
        key: A key of the ``"clues"`` mapping.

    Returns:
        A tuple ``(direction, heading)``, where ``heading`` is the
        direction itself if the key gives no other.
    """
    direction, _, heading = key.partition(":")
    return direction, heading or direction


def clue_group(clues, direction):
    """Finds the clue list for a direction, whatever heading it carries.

    Args:
        clues: The ``"clues"`` mapping from an ipuz file, or None.
        direction: The direction wanted, such as ``"Across"``.

    Returns:
        A tuple ``(key, clue_list)`` holding the key the direction is
        filed under and its clues, or ``(direction, [])`` if the file
        has no clues for that direction.
    """
    for key, group in (clues or {}).items():
        if split_direction(key)[0] == direction:
            return key, group
    return direction, []


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


def clue_heading(clue):
    """Works out what to print in front of a clue.

    Args:
        clue: A clue in ipuz form.

    Returns:
        The clue's ``"label"`` if it has one, otherwise its number, or
        its numbers joined with ampersands if it serves several
        entries. An empty string if the clue has none of these.
    """
    if isinstance(clue, dict):
        if clue.get("label") is not None:
            return str(clue["label"])
        if clue.get("number") is None and clue.get("numbers"):
            return " & ".join(str(number) for number in clue["numbers"])

    return clue_number(clue) or ""


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


def rebuild_clue(original, number, text):
    """Rebuilds a clue with a new number and text, keeping its format.

    A clue given as a mapping keeps its other fields, except those that
    name other clues or grid positions, which a new numbering would
    leave pointing at the wrong place.

    Args:
        original: The existing clue to rebuild.
        number: The entry number for the rebuilt clue.
        text: The clue text for the rebuilt clue.

    Returns:
        A clue in the same shape as ``original``.
    """
    if isinstance(original, dict):
        clue = {
            key: value
            for key, value in original.items()
            if key not in _CLUE_LINK_KEYS and key != "label"
        }
        clue["number"] = number
        clue["clue"] = text
        return clue
    return [number, text]


def plain_text(text):
    """Reduces an ipuz HTML string to plain text.

    ipuz text fields are HTML: they may use a small set of formatting
    tags, and write ``&``, ``<`` and ``>`` as character entities.

    Args:
        text: The HTML string, or None.

    Returns:
        The text with line breaks turned into spaces, formatting tags
        removed, and character entities decoded.
    """
    if text is None:
        return ""

    text = _LINE_BREAK.sub(" ", str(text))
    text = _FORMAT_TAG.sub("", text)
    return html.unescape(text)


def describe_feature(feature, details=()):
    """Names a feature for an error or warning message.

    Args:
        feature: One of this module's feature constants.
        details: The specifics found by :func:`detect_features`.

    Returns:
        The feature's description, followed in brackets by its details
        if there are any.
    """
    description = _FEATURE_DESCRIPTIONS[feature]
    if details:
        return f"{description} ({', '.join(sorted(details))})"
    return description


def detect_features(data):
    """Finds the optional ipuz crossword features a puzzle makes use of.

    Args:
        data: The parsed ipuz data, already checked by ``load_ipuz``.

    Returns:
        A dictionary mapping each feature constant found to a set of
        strings giving specifics, such as the style names or clue
        fields involved. The set is empty where there is nothing to add.
    """
    found = {}

    def add(feature, detail=None):
        details = found.setdefault(feature, set())
        if detail is not None:
            details.add(str(detail))

    block, empty = markers(data)
    named_styles = data.get("styles") if isinstance(data.get("styles"), dict) else {}

    def note_style(style):
        if isinstance(style, str):
            style = named_styles.get(style)
        if not isinstance(style, dict):
            return
        for key, value in style.items():
            if value is None or value == "" or value is False:
                continue
            if key in _BAR_STYLE_KEYS:
                add(BARS, key)
            elif key in _ORIENTED_STYLE_KEYS:
                add(ORIENTED_STYLES, key)
            else:
                add(STYLES, key)

    def has_many_values(value):
        if isinstance(value, list):
            return True
        if isinstance(value, dict):
            return any(key not in ("value", "style") for key in value) or isinstance(
                value.get("value"), list
            )
        return False

    puzzle = data["puzzle"]

    for row in puzzle:
        for cell in row:
            if isinstance(cell, dict):
                note_style(cell.get("style"))
                if cell.get("value") not in (None, ""):
                    add(GIVENS)

    for row in data.get("solution") or []:
        for cell in row:
            if isinstance(cell, dict):
                note_style(cell.get("style"))
            if has_many_values(cell):
                add(MULTI_VALUES)

    if data.get("zones"):
        add(ZONES)

    texts = [data.get("title"), data.get("author"), data.get("copyright")]

    for key, group in (data.get("clues") or {}).items():
        direction = split_direction(key)[0]
        if direction not in ("Across", "Down") and group:
            add(OTHER_DIRECTIONS, direction)

        for clue in group:
            texts.append(clue_text(clue))

            if not isinstance(clue, dict):
                if clue_number(clue) is None:
                    add(UNNUMBERED_CLUES)
                continue

            if clue.get("numbers"):
                add(MULTI_ENTRY_CLUES)
            elif clue.get("number") is None:
                add(UNNUMBERED_CLUES)
            if clue.get("cells"):
                add(CLUE_CELLS)
            if clue.get("label") is not None:
                add(CLUE_LABELS)
            for field in clue:
                if field in _CLUE_LINK_KEYS:
                    add(CLUE_LINKS, field)
                elif field not in _PLAIN_CLUE_KEYS:
                    add(CLUE_FIELDS, field)

    if any(isinstance(text, str) and _FORMAT_TAG.search(text) for text in texts):
        add(FORMATTING)

    standard = {
        entry["cells"][0]: str(entry["number"])
        for entry in extract_entries(puzzle, block, empty)
    }
    for r, row in enumerate(puzzle):
        for c, cell in enumerate(row):
            label = cell_label(cell, empty, block)
            if label and label != standard.get((r, c)):
                add(CUSTOM_LABELS)

    return found


def single_file_parser(description):
    """Builds an argument parser for a tool that reads one ipuz file.

    Args:
        description: The help text describing what the tool does.

    Returns:
        An ``argparse.ArgumentParser`` carrying a single positional
        ``ipuz_file`` argument.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("ipuz_file", help="Path to the .ipuz file to read.")
    return parser


def print_bar_chart(rows, rule_width, max_bar_width=40):
    """Prints a labelled horizontal bar chart between two rules.

    Bars are scaled down proportionally if the largest count would
    otherwise overflow ``max_bar_width``, and every non-zero count is
    given at least one block so that it stays visible.

    Args:
        rows: An iterable of ``(label, count)`` pairs, already sorted
            and with labels padded to a common width by the caller.
        rule_width: Width in characters of the horizontal rules drawn
            above and below the chart.
        max_bar_width: The longest bar to draw, in characters.

    Returns:
        None
    """
    rows = list(rows)
    if not rows:
        return

    max_count = max(count for _, count in rows)
    scale = max_bar_width / max_count if max_count > max_bar_width else 1

    print("-" * rule_width)
    for label, count in rows:
        bar = "█" * max(1, round(count * scale))
        print(f"{label} : {count:2} | {bar}")
    print("-" * rule_width)
