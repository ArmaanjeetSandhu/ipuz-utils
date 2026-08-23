"""Shared utilities for reading and analysing ipuz crossword files."""

import argparse
import json
import sys

BLOCK = "#"

_MISSING_MESSAGES = {
    "puzzle": "No puzzle grid found",
    "solution": "No solution grid found",
    "clues": "No clues found",
}


def load_ipuz(ipuz_file, require=()):
    """Loads and parses an ipuz file, checking that it has what is needed.

    Args:
        ipuz_file: Path to the .ipuz file to read.
        require: An iterable of top-level keys that must be present and
            non-empty, drawn from ``"puzzle"``, ``"solution"``, and
            ``"clues"``.

    Returns:
        The parsed puzzle data as a dictionary.

    Raises:
        SystemExit: If the file cannot be found, is not valid JSON, or
            lacks one of the required keys.
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

    for key in require:
        if not data.get(key):
            print(f"Error: {_MISSING_MESSAGES[key]} in '{ipuz_file}'.")
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


def make_is_playable(puzzle):
    """Returns an ``is_playable`` function bound to the given puzzle grid.

    The returned function determines whether a grid cell is a playable
    (white) square, i.e., within bounds, not None, and not a black
    square ("#").

    Args:
        puzzle: A 2-D list representing the crossword grid, as found
            in the ``"puzzle"`` key of an ipuz file.

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
            cell is neither None nor a black square ("#"); False
            otherwise.
        """
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return False

        try:
            cell = puzzle[r][c]
        except IndexError:
            return False

        if cell is None or cell == BLOCK:
            return False

        return True

    return is_playable


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


def cell_value(cell):
    """Unwraps the text held by an ipuz grid cell.

    An ipuz cell may be a bare string, a number, or a mapping carrying
    the letter under a ``"value"`` key alongside styling information.

    Args:
        cell: A single cell drawn from an ipuz grid.

    Returns:
        The cell's text as a string, or an empty string if the cell is
        empty or is a block.
    """
    if cell is None or cell == BLOCK:
        return ""

    if isinstance(cell, dict):
        cell = cell.get("value", "")

    if cell is None:
        return ""

    return str(cell)


def letter_at(solution, r, c):
    """Retrieves the uppercase solution letter at a grid cell.

    Args:
        solution: A 2-D list representing the solution grid.
        r: Zero-indexed row coordinate.
        c: Zero-indexed column coordinate.

    Returns:
        The uppercase letter occupying the cell, or an empty string if
        the cell is missing or empty.
    """
    try:
        cell = solution[r][c]
    except IndexError:
        return ""

    return cell_value(cell).upper()


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
