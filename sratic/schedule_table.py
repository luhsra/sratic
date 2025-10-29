import logging
from typing import override
import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from textwrap import dedent
import csv
import re
from datetime import datetime
import html


class SchedulePreprocessor(Preprocessor):
    # Regular expression to match fenced code blocks from fenced_code extension.
    FENCED_BLOCK_RE: re.Pattern[str] = re.compile(
        dedent(
            r"""
            (?P<indent>^[ \t]*)
            (?P<fence>(?:~{3,}|`{3,}))[ ]*                           # opening fence
            ((\{(?P<attrs>[^\n]*)\})|                                # (optional {attrs} or
            (\.?(?P<lang>[\w#.+-]*)[ ]*)?                            # optional (.)lang
            (hl_lines=(?P<quot>"|')(?P<hl_lines>.*?)(?P=quot)[ ]*)?) # optional hl_lines)
            \n                                                       # newline (end of opening fence)
            (?P<code>.*?)(?<=\n)                                     # the code block
            (?P=indent)(?P=fence)[ ]*$                               # closing fence
        """
        ),
        re.MULTILINE | re.DOTALL | re.VERBOSE,
    )

    @override
    def run(self, lines: list[str]):
        text = "\n".join(lines)
        new_text = ""
        pos = 0
        for match in self.FENCED_BLOCK_RE.finditer(text):
            start, end = match.span()
            indent = match.group("indent")
            code = match.group("code")
            lang = match.group("lang") or ""
            attrs = match.group("attrs") or ""
            # Append text before this block
            new_text += text[pos:start]

            # Process Schedule code blocks with preview
            if lang.strip() == "schedule":
                logging.info("Found Schedule code block")
                table_html = table_from_csv(code)
                if not table_html:
                    continue
                new_text += indent + table_html
            else:
                # Keep as fenced code block
                new_text += match.group(0)
            pos = end

        if pos == 0:
            return lines  # No changes

        # Append any remaining text
        new_text += text[pos:]
        return new_text.splitlines()


def table_from_csv(code: str) -> str:
    # Generate html table from schedule data (csv)
    # Header is expected to be: KW,Weekday1,Weekday2,...
    csv_reader = csv.reader(code.strip().splitlines())
    rows = list(csv_reader)
    if not rows:
        return ""

    header = f'<tr><th><small class="text-muted">KW: </small>Datum</th>'
    for cell in rows[0][1:]:
        header += f"<th>{html.escape(cell)}</th>"
    header += "</tr>"
    body = ""
    for row in rows[1:]:
        wdate, cells = row[0].strip(), row[1:]
        pdate = datetime.strptime(wdate, "%d.%m.%y").date()
        kw = pdate.isocalendar().week
        body += f'<tr><td><small class="text-muted">{kw}: </small>{wdate}</td>'

        for cell in cells[:-1]:
            body += f"<td>{format_cell(cell)}</td>"
        body += (
            f'<td colspan="{1 + len(rows[0]) - len(row)}">{format_cell(cells[-1])}</td>'
        )

        body += "</tr>"

    return f'<table class="table table-striped table-responsive semester-schedule"><thead>{header}</thead><tbody>{body}</tbody></table>'


def format_cell(cell: str) -> str:
    cell = html.escape(cell.strip())
    if m := re.match(r"^(V|S)(\d+): ", cell):
        return (
            f'<span class="label label-primary">{m.group(1)}{m.group(2)}</span> {cell[m.end() :]}'
        )
    elif m := re.match(r"^U(\d+): ", cell):
        return f'<span class="label label-info">U{m.group(1)}</span> {cell[m.end() :]}'
    elif m := re.match(r"^A(\d+): ", cell):
        return (
            f'<span class="label label-success">A{m.group(1)}</span> {cell[m.end() :]}'
        )
    elif m := re.match(r"^D: ", cell):
        return f'<span class="label label-danger" style="display:inline-block;width:100%">Deadline: {cell[m.end():]}</span>'
    elif m := re.match(r"^R$", cell):
        return f'<span class="label label-warning">R</span> Rechnerübung'
    elif cell == "Repetitorium":
        return f'<span class="label label-warning">Repetitorium</span>'
    return cell


class ScheduleExtension(Extension):
    @override
    def extendMarkdown(self, md: markdown.Markdown):
        md.registerExtension(self)
        md.preprocessors.register(SchedulePreprocessor(md), "schedule", 40)


def schedule_table(path: str) -> str:
    # TODO: Relative file path?
    logging.info(f"Loading schedule from {path}")
    with open(path, "r") as f:
        code = f.read()
    return table_from_csv(code)
