import argparse
import math
import os
import random
import struct
import sys
import textwrap

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfdoc, pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen import canvas

from shared import (
    BARS,
    CLUE_FIELDS,
    CLUE_LINKS,
    FORMATTING,
    GIVENS,
    MULTI_VALUES,
    ORIENTED_STYLES,
    STYLES,
    ZONES,
    cell_label,
    cell_value,
    clue_heading,
    clue_text,
    is_block,
    is_circled,
    is_omitted,
    load_ipuz,
    markers,
    named_styles,
    plain_text,
    split_direction,
)

UNPRINTED_FIELDS = (
    "intro",
    "notes",
    "publisher",
    "publication",
    "editor",
    "date",
    "difficulty",
    "showenumerations",
    "clueplacement",
)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
PAPER_FONT = os.path.join(ASSETS_DIR, "font.ttf")
PAPER_FONT_NAME = "PaperFont"

PAPER_TONE = (0.903, 0.899, 0.91)

PAPER_BUMPS = {
    "density": 0.1,
    "radius": (0.6, 1.9),
    "sides": 6,
    "relief": 0.35,
    "dark": (0.05, 0.09),
    "light": (0.25, 0.4),
}
PAPER_FINE_FLECKS = {
    "density": 2.0,
    "radius": (0.12, 0.42),
    "dark": (0.05, 0.09, 0.14),
    "light": (0.35, 0.6, 0.85),
}
PAPER_FLECKS = {
    "density": 0.6,
    "radius": (0.25, 0.7),
    "dark": (0.03, 0.06),
    "light": (0.25, 0.45),
}

PAPER_GRAIN = (
    {"tile": 29, "angle": 17, "specks": (PAPER_BUMPS,)},
    {"tile": 37, "angle": -29, "specks": (PAPER_BUMPS,)},
    {"tile": 31, "angle": 61, "specks": (PAPER_FINE_FLECKS, PAPER_FLECKS)},
)

PAPER_MOTTLES = 70
PAPER_MOTTLE_RADIUS = (25, 90)
PAPER_MOTTLE_STRENGTH = (0.08, 0.11)
PAPER_MESH_STEP = 12

PAPER_SEED = 7
PAPER_GRAIN_FORM = "PaperGrain"
SPECK_UNITS = 100

GRID_LINE_WIDTH = 1

NUMBER_FONT = "Helvetica-Bold"
NUMBER_INSET = 1.5

CIRCLE_WIDTH = 0.035
CIRCLE_MIN_WIDTH = 0.5
CIRCLE_CLEARANCE = 0.035


def number_font_size(cell_size):
    """Work out the size of the clue number printed in a cell.

    Args:
        cell_size (float): Side of a grid cell in points.

    Returns:
        int: The font size in points.
    """
    return max(5, int(cell_size / 4.5))


def draw_circle(c, x, y, cell_size, label=None):
    """Draw the circle of a circled square.

    The circle is the largest that fits inside the cell's border. Where the cell's
    clue number would overlap it, the arc behind the number is left out, so the number
    sits clear of the circle with the rest of the circle unbroken.

    The number occupies a box in the top left corner of the cell. Where the corner of
    that box nearest the centre lies on or outside the circle, the circle never meets
    the box and is drawn whole. Otherwise the circle crosses the box's right edge near
    the top of the cell and its bottom edge near the left, and the arc between those
    two points is the part that is left out.

    Args:
        c (canvas.Canvas): The canvas to draw on.
        x (float): X coordinate of the cell's lower left corner.
        y (float): Y coordinate of the cell's lower left corner.
        cell_size (float): Side of the cell in points.
        label (str, optional): The clue number printed in the cell, if any.

    Returns:
        None
    """
    width = max(CIRCLE_MIN_WIDTH, cell_size * CIRCLE_WIDTH)
    radius = (cell_size - GRID_LINE_WIDTH - width) / 2
    cx = x + cell_size / 2
    cy = y + cell_size / 2

    arc = None
    if label:
        font_size = number_font_size(cell_size)
        clearance = CIRCLE_CLEARANCE * cell_size + width / 2
        right = (
            NUMBER_INSET
            + c.stringWidth(label, NUMBER_FONT, font_size)
            + clearance
            - cell_size / 2
        )
        bottom = font_size + clearance - cell_size / 2
        if right * right + bottom * bottom < radius * radius:
            start = 2 * math.pi - math.acos(right / radius)
            end = 3 * math.pi - math.asin(bottom / radius)
            arc = (-math.degrees(end), math.degrees(end - start))

    c.saveState()
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(width)
    c.setLineCap(1)
    if arc:
        c.arc(cx - radius, cy - radius, cx + radius, cy + radius, *arc)
    else:
        c.circle(cx, cy, radius, stroke=1, fill=0)
    c.restoreState()


def load_paper_font():
    """Register the font used for solution letters in the paper look.

    Returns:
        None

    Raises:
        SystemExit: If the font is missing or cannot be read; the program prints an
            error message and exits with status code 1.
    """
    try:
        pdfmetrics.registerFont(TTFont(PAPER_FONT_NAME, PAPER_FONT))
    except TTFError:
        print(f"Error: '{PAPER_FONT}' is missing or is not a usable TrueType font.")
        sys.exit(1)


def paper_shade(toward, strength):
    """Blend the paper tone toward black or white.

    Args:
        toward (float): 0.0 to darken toward black, 1.0 to lighten toward white.
        strength (float): How far to blend, from 0.0 (paper) to 1.0 (`toward`).

    Returns:
        tuple[float, float, float]: The blended RGB colour.
    """
    return tuple(t + (toward - t) * strength for t in PAPER_TONE)


def make_grain_pattern(rng, tile, angle, specks):
    """Build one grain pattern as a PDF tiling pattern.

    The specks are generated into one tile, which the viewer repeats across whatever
    area the pattern fills. A speck that crosses an edge of the tile is also drawn on
    the opposite edge, so the tile joins its neighbours without a seam. Specks of the
    same colour are gathered into one path, so the whole tile is only a handful of fill
    operations.

    Args:
        rng (random.Random): Source of randomness for speck placement.
        tile, angle, specks: The pattern's settings; see ``PAPER_GRAIN``.

    Returns:
        PDFStream: The pattern, ready to add to a document.
    """
    content = [f"{1 / SPECK_UNITS} 0 0 {1 / SPECK_UNITS} 0 0 cm"]

    def add_speck(path, x, y, corners, reach):
        for dx in (-tile, 0, tile):
            for dy in (-tile, 0, tile):
                cx, cy = x + dx, y + dy
                if -reach <= cx <= tile + reach and -reach <= cy <= tile + reach:
                    points = [
                        (round((cx + px) * SPECK_UNITS), round((cy + py) * SPECK_UNITS))
                        for px, py in corners
                    ]
                    path.append(
                        f"{points[0][0]} {points[0][1]} m "
                        + " ".join(f"{px} {py} l" for px, py in points[1:])
                        + " h"
                    )

    for kind in specks:
        dark, light = kind["dark"], kind["light"]
        sides, relief = kind.get("sides", 4), kind.get("relief", 0)
        colors = [paper_shade(0.0, s) for s in dark]
        colors += [paper_shade(1.0, s) for s in light]
        paths = [[] for _ in colors]

        step = 2 * math.pi / sides
        for _ in range(int(kind["density"] * tile * tile)):
            r = rng.uniform(*kind["radius"])
            x, y = rng.uniform(0, tile), rng.uniform(0, tile)
            start = rng.uniform(0, 2 * math.pi)
            corners = []
            for i in range(sides):
                a = start + step * (i + rng.uniform(-0.3, 0.3))
                d = r * rng.uniform(0.6, 1.0)
                corners.append((d * math.cos(a), d * math.sin(a)))

            if relief:
                shift = relief * r
                shadow = paths[rng.randrange(len(dark))]
                highlight = paths[len(dark) + rng.randrange(len(light))]
                add_speck(shadow, x + shift, y - shift, corners, r + shift)
                add_speck(highlight, x - shift, y + shift, corners, r + shift)
            else:
                add_speck(paths[rng.randrange(len(colors))], x, y, corners, r)

        for color, path in zip(colors, paths, strict=False):
            if path:
                content.append("{:.4f} {:.4f} {:.4f} rg".format(*color))
                content.extend(path)
                content.append("f")

    cos = round(math.cos(math.radians(angle)), 6)
    sin = round(math.sin(math.radians(angle)), 6)
    return pdfdoc.PDFStream(
        dictionary=pdfdoc.PDFDictionary(
            {
                "Type": pdfdoc.PDFName("Pattern"),
                "PatternType": 1,
                "PaintType": 1,
                "TilingType": 1,
                "BBox": pdfdoc.PDFArray([0, 0, tile, tile]),
                "XStep": tile,
                "YStep": tile,
                "Matrix": pdfdoc.PDFArray([cos, sin, -sin, cos, 0, 0]),
                "Resources": pdfdoc.PDFDictionary({}),
            }
        ),
        content="\n".join(content),
        filters=[pdfdoc.PDFZCompress],
    )


def make_mottled_tone(rng, page_width, page_height):
    """Build the paper tone and its mottling as one smooth mesh gradient.

    Scatters soft patches over the page, adds up how much they darken or lighten each
    corner of a fine grid, and gives the viewer the colour at every corner. The viewer
    shades smoothly between corners, so there are no edges to see at any zoom, and the
    whole page is one operation.

    The shading object is written by hand: a lattice-form Gouraud-shaded triangle mesh
    (shading type 5), with each corner packed as 16-bit coordinates and colours.

    Args:
        rng (random.Random): Source of randomness for the patches.
        page_width (float): Width of the page in points.
        page_height (float): Height of the page in points.

    Returns:
        PDFStream: The shading, ready to paint with ``canvas.shade``.
    """
    patches = []
    for _ in range(PAPER_MOTTLES):
        r = rng.uniform(*PAPER_MOTTLE_RADIUS)
        x = rng.uniform(-r / 2, page_width + r / 2)
        y = rng.uniform(-r / 2, page_height + r / 2)
        darken = rng.random() < 0.5
        strength = PAPER_MOTTLE_STRENGTH[0 if darken else 1] * rng.uniform(0.3, 1.0)
        patches.append((x, y, r, -strength if darken else strength))

    cols = math.ceil(page_width / PAPER_MESH_STEP) + 1
    rows = math.ceil(page_height / PAPER_MESH_STEP) + 1
    top = 0xFFFF
    data = bytearray()
    for j in range(rows):
        y = page_height * j / (rows - 1)
        for i in range(cols):
            x = page_width * i / (cols - 1)
            shift = 0.0
            for px, py, r, strength in patches:
                d2 = ((x - px) ** 2 + (y - py) ** 2) / (r * r)
                if d2 < 1:
                    shift += strength * (1 - d2) ** 2
            color = paper_shade(0.0 if shift < 0 else 1.0, min(abs(shift), 1.0))
            data += struct.pack(
                ">5H",
                round(top * i / (cols - 1)),
                round(top * j / (rows - 1)),
                *(round(top * channel) for channel in color),
            )

    return pdfdoc.PDFStream(
        dictionary=pdfdoc.PDFDictionary(
            {
                "ShadingType": 5,
                "ColorSpace": pdfdoc.PDFName("DeviceRGB"),
                "BitsPerCoordinate": 16,
                "BitsPerComponent": 16,
                "VerticesPerRow": cols,
                "Decode": pdfdoc.PDFArray(
                    [0, page_width, 0, page_height, 0, 1, 0, 1, 0, 1]
                ),
            }
        ),
        content=bytes(data),
        filters=[pdfdoc.PDFZCompress],
    )


def define_paper(c, page_width, page_height):
    """Prepare the paper grain once for the whole document.

    Defines the grain patterns, and a form that fills the page with each of them in
    turn, so every page can draw the grain with a single reference to that form.

    Args:
        c (canvas.Canvas): The canvas to prepare.
        page_width (float): Width of the page in points.
        page_height (float): Height of the page in points.

    Returns:
        random.Random: Source of randomness for the per-page mottling, seeded so that
            the same puzzle always gives the same PDF.
    """
    rng = random.Random(PAPER_SEED)
    patterns = {}
    for i, settings in enumerate(PAPER_GRAIN):
        pattern = make_grain_pattern(rng, **settings)
        patterns[f"Grain{i}"] = c._doc.Reference(pattern, f"PaperGrainPattern{i}")

    c.beginForm(PAPER_GRAIN_FORM, 0, 0, page_width, page_height)
    for name in patterns:
        c.addLiteral(f"/Pattern cs /{name} scn 0 0 {page_width} {page_height} re f")
    c.endForm()

    form = c._doc.idToObject[c._doc.getXObjectName(PAPER_GRAIN_FORM)]
    form.Resources = pdfdoc.PDFResourceDictionary(Pattern=patterns)
    return rng


def draw_paper(c, page_width, page_height, rng):
    """Cover the current page with the paper look.

    Paints the paper tone with a different mottling on each page, then the grain
    prepared by ``define_paper``.

    Args:
        c (canvas.Canvas): The canvas to draw on, already prepared with
            ``define_paper``.
        page_width (float): Width of the page in points.
        page_height (float): Height of the page in points.
        rng (random.Random): Source of randomness for the mottling.

    Returns:
        None
    """
    c.saveState()
    c.shade(make_mottled_tone(rng, page_width, page_height))
    c.doForm(PAPER_GRAIN_FORM)
    c.restoreState()


def create_crossword_pdf(
    ipuz_file, pdf_file, orientation="right", show_solution=False, paper=False
):
    """Render an ipuz crossword puzzle as a formatted PDF.

    Reads a crossword puzzle in ipuz JSON format, draws the title, author, and copyright
    line, then lays out the puzzle grid alongside its clue lists, wrapping clues into
    columns and spilling onto additional pages as needed. Can optionally fill in the
    solution.

    Blocks are recognised by the file's own block marker, and cells that ipuz marks as
    omitted are left undrawn. Circled squares are drawn with a circle inscribed in the
    square, which omits the arc behind the square's clue number. Parts of the puzzle
    that the PDF cannot show, such as other cell styles, are reported in a warning, and
    a puzzle that relies on bars between cells is refused.

    Args:
        ipuz_file (str): Path to the input .ipuz JSON file.
        pdf_file (str): Path where the generated PDF will be saved.
        orientation (str, optional): Layout orientation for the grid. Use "left" to
            place the grid on the left side of the page with clues to its right, or
            "right" (the default) to place the grid on the right side of the page with
            clues to its left.
        show_solution (bool, optional): Whether to fill the grid with the solution.
        paper (bool, optional): Whether to give the PDF a paper look: every page is
            backed by a textured paper, drawn in vector graphics, which shows through
            the open cells of the grid. The solution letters are set in
            ``assets/font.ttf``, which is looked up next to this script.

    Returns:
        None

    Raises:
        SystemExit: If `ipuz_file` cannot be found, cannot be parsed, or uses a feature
            that cannot be drawn, or if the paper font is needed but missing or
            unreadable; the program prints an error message and exits with status code 1
    """
    data = load_ipuz(
        ipuz_file,
        require=("puzzle",),
        reject=(BARS, MULTI_VALUES) if show_solution else (BARS,),
        warn={
            STYLES: "not drawn",
            ORIENTED_STYLES: "not drawn",
            GIVENS: "not drawn",
            ZONES: "not drawn",
            FORMATTING: "shown as plain text",
            CLUE_LINKS: "not shown",
            CLUE_FIELDS: "not shown",
        },
        unused_fields=(UNPRINTED_FIELDS, "not shown"),
    )

    directory = os.path.dirname(pdf_file)
    if directory:
        os.makedirs(directory, exist_ok=True)

    if paper and show_solution:
        load_paper_font()
    letter_font = PAPER_FONT_NAME if paper else "Helvetica-Bold"
    letter_color = (0.15, 0.15, 0.15) if paper else (0.3, 0.3, 0.3)

    c = canvas.Canvas(pdf_file, pagesize=letter)
    page_width, page_height = letter
    paper_rng = define_paper(c, page_width, page_height) if paper else None

    def draw_background():
        """Cover the current page with the paper look, if it is in use.

        Returns:
            None
        """
        if paper:
            draw_paper(c, page_width, page_height, paper_rng)

    draw_background()

    title = "Crossword Puzzle"
    if data.get("title") is not None:
        title = plain_text(data["title"])
    author = plain_text(data.get("author"))
    copyright_text = plain_text(data.get("copyright"))

    cols = data["dimensions"]["width"]
    rows = data["dimensions"]["height"]
    puzzle = data["puzzle"]
    solution = data.get("solution") or []
    block, empty = markers(data)
    styles = named_styles(data)

    current_y = page_height - 40

    c.setFont("Times-Bold", 16)
    c.drawString(30, current_y, title)
    current_y -= 16

    c.setFont("Times-Roman", 10)
    c.drawString(30, current_y, author)
    current_y -= 12

    if copyright_text:
        c.setFont("Times-Italic", 8)
        c.drawString(30, current_y, copyright_text)
        current_y -= 12

    current_y -= 2
    c.setLineWidth(1)
    c.line(30, current_y, page_width - 30, current_y)

    content_start_y = current_y - 20

    grid_width_points = 270
    cell_size = grid_width_points / cols
    grid_height_points = cell_size * rows

    right_area_x = page_width - 30 - grid_width_points

    start_x_grid = 30 if orientation == "left" else right_area_x

    start_y_grid = content_start_y - grid_height_points

    c.setLineWidth(GRID_LINE_WIDTH)
    for r in range(rows):
        for col in range(cols):
            cell_val = puzzle[r][col]

            if is_omitted(cell_val):
                continue

            x = start_x_grid + col * cell_size
            y = start_y_grid + (rows - 1 - r) * cell_size

            if is_block(cell_val, block):
                c.setFillColorRGB(0, 0, 0)
                c.rect(x, y, cell_size, cell_size, fill=1)
            else:
                c.setFillColorRGB(1, 1, 1)
                c.rect(x, y, cell_size, cell_size, fill=0 if paper else 1)
                c.setFillColorRGB(0, 0, 0)

                label = cell_label(cell_val, empty, block)
                if is_circled(cell_val, styles):
                    draw_circle(c, x, y, cell_size, label)

                if show_solution and r < len(solution) and col < len(solution[r]):
                    sol_char = cell_value(solution[r][col], block, empty)
                    if sol_char:
                        letter_font_size = max(8, int(cell_size / 1.5))
                        c.setFont(letter_font, letter_font_size)

                        letter_width = c.stringWidth(
                            sol_char, letter_font, letter_font_size
                        )
                        lx = x + (cell_size - letter_width) / 2
                        ly = y + (cell_size - letter_font_size) / 2

                        c.setFillColorRGB(*letter_color)
                        c.drawString(lx, ly, sol_char)
                        c.setFillColorRGB(0, 0, 0)

                if label:
                    font_size = number_font_size(cell_size)
                    c.setFont(NUMBER_FONT, font_size)
                    c.drawString(x + NUMBER_INSET, y + cell_size - font_size, label)

    clue_groups = []
    for key, clues in (data.get("clues") or {}).items():
        direction, heading = split_direction(key)
        clue_groups.append((direction, plain_text(heading), clues))

    lead = {"Across": 0, "Down": 1}
    clue_groups.sort(key=lambda group: lead.get(group[0], 2))

    def draw_all_clues(groups):
        """Lay out and draw the puzzle's clue lists on the canvas.

        Arranges clues into a fixed set of columns whose positions depend on the chosen
        grid orientation, drawing a section header for each clue list followed by its
        clues. Delegates to nested helpers to handle column/page wrapping and text
        drawing.

        Args:
            groups (list[tuple]): ``(direction, heading, clues)`` for each clue list, in
                the order to draw them, where ``heading`` is the text to print above the
                list and ``clues`` holds its clues in any ipuz clue format.

        Returns:
            None
        """
        if orientation == "left":
            columns = [
                {"x": 30, "y": start_y_grid - 20},
                {"x": 165, "y": start_y_grid - 20},
                {"x": right_area_x, "y": content_start_y},
                {"x": right_area_x + 135, "y": content_start_y},
            ]
        else:
            columns = [
                {"x": 30, "y": content_start_y},
                {"x": 165, "y": content_start_y},
                {"x": right_area_x, "y": start_y_grid - 20},
                {"x": right_area_x + 135, "y": start_y_grid - 20},
            ]

        col_idx = 0
        current_x = columns[col_idx]["x"]
        current_y_clue = columns[col_idx]["y"]

        line_height = 10
        clue_spacing = 2
        max_width_chars = 28

        def check_page_wrap(needed_space=0):
            """Advance to the next clue column or a new page if space is short.

            Checks whether the remaining vertical space in the current column can fit
            `needed_space` points of content. If not, advances to the next predefined
            column; if no columns remain, starts a new PDF page with a fresh set of four
            columns.

            Args:
                needed_space (int, optional): Vertical space in points required for the
                    upcoming content. Defaults to 0.

            Returns:
                None
            """
            nonlocal current_x, current_y_clue, col_idx, columns
            if (current_y_clue - needed_space) < 50:
                col_idx += 1
                if col_idx < len(columns):
                    current_x = columns[col_idx]["x"]
                    current_y_clue = columns[col_idx]["y"]
                else:
                    c.showPage()
                    draw_background()
                    columns = [
                        {"x": 30, "y": page_height - 50},
                        {"x": 165, "y": page_height - 50},
                        {"x": 300, "y": page_height - 50},
                        {"x": 435, "y": page_height - 50},
                    ]
                    col_idx = 0
                    current_x = columns[col_idx]["x"]
                    current_y_clue = columns[col_idx]["y"]

        def draw_header(text):
            """Draw a bold section header with an underline below it.

            Args:
                text (str): Header text to draw (e.g. "Across" or "Down").

            Returns:
                None
            """
            nonlocal current_y_clue
            check_page_wrap(line_height * 3)
            c.setFont("Times-Bold", 12)
            c.drawString(current_x, current_y_clue, text)

            text_width = c.stringWidth(text, "Times-Bold", 12)
            c.setLineWidth(0.5)
            c.line(
                current_x,
                current_y_clue - 1.5,
                current_x + text_width,
                current_y_clue - 1.5,
            )

            current_y_clue -= line_height + clue_spacing + 2.5

        def draw_clue_list(clues):
            """Draw a numbered, word-wrapped list of clues.

            Each clue is prefixed with its number (or its label, if the file gives one)
            in bold, word-wrapped to fit the column width, and drawn line by line,
            wrapping to a new column or page as needed. A clue with neither is drawn
            without a prefix.

            Args:
                clues (list): Clue entries in any ipuz clue format.

            Returns:
                None
            """
            nonlocal current_y_clue
            for clue in clues:
                num = clue_heading(clue)
                text = plain_text(clue_text(clue))

                num_prefix = f"{num}. " if num else ""
                wrapped_text = textwrap.wrap(
                    f"{num_prefix}{text}", width=max_width_chars
                )

                for i, line in enumerate(wrapped_text):
                    check_page_wrap(line_height)

                    if i == 0 and num:
                        c.setFont("Times-Bold", 9)
                        c.drawString(current_x, current_y_clue, num_prefix)

                        num_width = c.stringWidth(num_prefix, "Times-Bold", 9)

                        rest_of_line = line[len(num_prefix) :]
                        c.setFont("Times-Roman", 9)
                        c.drawString(
                            current_x + num_width, current_y_clue, rest_of_line
                        )
                    else:
                        c.setFont("Times-Roman", 9)
                        c.drawString(current_x, current_y_clue, line)

                    current_y_clue -= line_height

                current_y_clue -= clue_spacing

        drawn_any = False
        for direction, heading, clues in groups:
            if not clues:
                continue

            if drawn_any or direction == "Down":
                current_y_clue -= 6

            draw_header(heading)
            draw_clue_list(clues)
            drawn_any = True

    draw_all_clues(clue_groups)

    c.save()
    print(f"Successfully created {pdf_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert an ipuz crossword puzzle file into a formatted PDF."
    )
    parser.add_argument("ipuz_file", help="Path to the input .ipuz JSON file.")
    parser.add_argument(
        "--out",
        default=None,
        help="Path where the generated PDF will be saved (default: <name>.pdf, or <name>_solution.pdf in solution mode).",
    )
    parser.add_argument(
        "orientation",
        nargs="?",
        default="right",
        choices=["left", "right"],
        help='Grid orientation: "left" or "right" (default: "right").',
    )
    parser.add_argument(
        "-s",
        "--solution",
        action="store_true",
        help="Generate the PDF in solution mode (grid filled out).",
    )
    parser.add_argument(
        "--paper",
        action="store_true",
        help="Print in paper mode.",
    )

    args = parser.parse_args()

    out_file = args.out
    if out_file is None:
        stem = os.path.splitext(os.path.basename(args.ipuz_file))[0]
        suffix = "_solution" if args.solution else ""
        out_file = f"{stem}{suffix}.pdf"

    create_crossword_pdf(
        args.ipuz_file, out_file, args.orientation, args.solution, args.paper
    )
