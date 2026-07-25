import json
import html
import textwrap
import sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_crossword_pdf(ipuz_file, pdf_file):
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

    start_x_grid = page_width - 30 - grid_width_points
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
                    c.setFont("Helvetica", max(5, int(cell_size / 3.5)))
                    c.drawString(
                        x + 2, y + cell_size - max(7, int(cell_size / 3)), str(cell_val)
                    )

    across_clues = data.get("clues", {}).get("Across", [])
    down_clues = data.get("clues", {}).get("Down", [])

    def draw_all_clues(across, down):
        columns = [
            {"x": 30, "y": content_start_y},
            {"x": 165, "y": content_start_y},
            {"x": start_x_grid, "y": start_y_grid - 20},
            {"x": start_x_grid + 135, "y": start_y_grid - 20},
        ]

        col_idx = 0
        current_x = columns[col_idx]["x"]
        current_y_clue = columns[col_idx]["y"]

        line_height = 10
        clue_spacing = 2
        max_width_chars = 28

        def check_page_wrap(needed_space=0):
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

            current_y_clue -= line_height + clue_spacing

        def draw_clue_list(clues):
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
