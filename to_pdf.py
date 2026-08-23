import argparse
import json
import html
import textwrap
import sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_crossword_pdf(ipuz_file, pdf_file, orientation="right", show_solution=False):
    """Render an ipuz crossword puzzle as a formatted PDF.

    Reads a crossword puzzle in ipuz JSON format, draws the title, author,
    and copyright line, then lays out the puzzle grid alongside the Across
    and Down clue lists, wrapping clues into columns and spilling onto
    additional pages as needed. Can optionally fill in the solution.

    Args:
        ipuz_file (str): Path to the input .ipuz JSON file.
        pdf_file (str): Path where the generated PDF will be saved.
        orientation (str, optional): Layout orientation for the grid.
            Use "left" to place the grid on the left side of the page
            with clues to its right, or "right" (the default) to place
            the grid on the right side of the page with clues to its left.
        show_solution (bool, optional): Whether to fill the grid with the solution.

    Returns:
        None

    Raises:
        SystemExit: If `ipuz_file` cannot be found; the program prints an
            error message and exits with status code 1.
    """
    try:
        with open(ipuz_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find the file {ipuz_file}")
        sys.exit(1)

    c = canvas.Canvas(pdf_file, pagesize=letter)
    page_width, page_height = letter

    title = data.get("title", "Crossword Puzzle")
    author = data.get("author", "")
    copyright_text = data.get("copyright", "")

    dims = data.get("dimensions", {"width": 15, "height": 15})
    cols = dims["width"]
    rows = dims["height"]
    puzzle = data.get("puzzle", [])
    solution = data.get("solution", [])

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

    if orientation == "left":
        start_x_grid = 30
    else:
        start_x_grid = right_area_x

    start_y_grid = content_start_y - grid_height_points

    c.setLineWidth(1)
    for r in range(rows):
        for col in range(cols):
            if r < len(puzzle) and col < len(puzzle[r]):
                cell_val = puzzle[r][col]
            else:
                cell_val = "#"

            x = start_x_grid + col * cell_size
            y = start_y_grid + (rows - 1 - r) * cell_size

            if cell_val == "#":
                c.setFillColorRGB(0, 0, 0)
                c.rect(x, y, cell_size, cell_size, fill=1)
            else:
                c.setFillColorRGB(1, 1, 1)
                c.rect(x, y, cell_size, cell_size, fill=1)
                c.setFillColorRGB(0, 0, 0)

                if isinstance(cell_val, int):
                    font_size = max(5, int(cell_size / 4.5))
                    c.setFont("Helvetica", font_size)
                    c.drawString(x + 1.5, y + cell_size - font_size, str(cell_val))

                if show_solution and r < len(solution) and col < len(solution[r]):
                    sol_val = solution[r][col]
                    if sol_val and sol_val != "#":
                        if isinstance(sol_val, dict):
                            sol_val = sol_val.get("value", "")

                        sol_char = str(sol_val)
                        letter_font_size = max(8, int(cell_size / 1.5))
                        c.setFont("Helvetica-Bold", letter_font_size)

                        letter_width = c.stringWidth(
                            sol_char, "Helvetica-Bold", letter_font_size
                        )
                        lx = x + (cell_size - letter_width) / 2
                        ly = y + (cell_size - letter_font_size) / 2

                        c.setFillColorRGB(0.3, 0.3, 0.3)
                        c.drawString(lx, ly, sol_char)
                        c.setFillColorRGB(0, 0, 0)

    across_clues = data.get("clues", {}).get("Across", [])
    down_clues = data.get("clues", {}).get("Down", [])

    def draw_all_clues(across, down):
        """Lay out and draw the Across and Down clue lists on the canvas.

        Arranges clues into a fixed set of columns whose positions depend
        on the chosen grid orientation, drawing "Across" and "Down"
        section headers followed by their respective clue lists. Delegates
        to nested helpers to handle column/page wrapping and text drawing.

        Args:
            across (list[dict]): Across clue entries, each expected to have
                "number" and "clue" keys.
            down (list[dict]): Down clue entries, each expected to have
                "number" and "clue" keys.

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

            Checks whether the remaining vertical space in the current
            column can fit `needed_space` points of content. If not,
            advances to the next predefined column; if no columns remain,
            starts a new PDF page with a fresh set of four columns.

            Args:
                needed_space (int, optional): Vertical space in points
                    required for the upcoming content. Defaults to 0.

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

            Each clue is prefixed with its number in bold, word-wrapped to
            fit the column width, and drawn line by line, wrapping to a new
            column or page as needed.

            Args:
                clues (list[dict]): Clue entries, each expected to have
                    "number" and "clue" keys.

            Returns:
                None
            """
            nonlocal current_y_clue
            for clue in clues:
                num = str(clue.get("number", ""))
                text = html.unescape(clue.get("clue", ""))

                num_prefix = f"{num}. "
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

        if across:
            draw_header("Across")
            draw_clue_list(across)

        if down:
            current_y_clue -= 6
            draw_header("Down")
            draw_clue_list(down)

    draw_all_clues(across_clues, down_clues)

    c.save()
    print(f"Successfully created {pdf_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert an ipuz crossword puzzle file into a formatted PDF."
    )
    parser.add_argument("ipuz_file", help="Path to the input .ipuz JSON file.")
    parser.add_argument("pdf_file", help="Path where the generated PDF will be saved.")
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

    args = parser.parse_args()

    create_crossword_pdf(args.ipuz_file, args.pdf_file, args.orientation, args.solution)
