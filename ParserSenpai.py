"""
    ParserSenpai
    - Parser for GGSIPU result PDFs
    Author: martian0x80
"""

import argparse
import json
import re
from itertools import groupby
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from multiprocessing import Manager, Pool

import pandas as pd
import pdfplumber
from pdfplumber.page import Page
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress

PDF_PATH = "RESULT_BTECH7_DEC2023.pdf"
RESULT_PATH = "result.txt"
SCHEME_PATH = "scheme.txt"

semHeaderMap = {
    "TENTH SEMESTER": 10,
    "NINTH SEMESTER": 9,
    "EIGHTH SEMESTER": 8,
    "SEVENTH SEMESTER": 7,
    "SIXTH SEMESTER": 6,
    "FIFTH SEMESTER": 5,
    "FOURTH SEMESTER": 4,
    "THIRD SEMESTER": 3,
    "SECOND SEMESTER": 2,
    "FIRST SEMESTER": 1,
    "01 SEMESTER": 1,
    "02 SEMESTER": 2,
    "03 SEMESTER": 3,
    "04 SEMESTER": 4,
    "05 SEMESTER": 5,
    "06 SEMESTER": 6,
    "07 SEMESTER": 7,
    "08 SEMESTER": 8,
    "09 SEMESTER": 9,
    "10 SEMESTER": 10,
}


progress = Progress()
console = Console()

parser = argparse.ArgumentParser(
    prog="IPU Results PDF Parser by martian0x80",
    description="Parses the IPU results pdf to generate meaningful data for export and data pipelines\nAuthor: martian0x80",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

parser.add_argument(
    "-os",
    "--output-scheme",
    action="store",
    dest="output_scheme",
    default=SCHEME_PATH,
    help="Output the scheme data here (txt)",
)

parser.add_argument(
    "-or",
    "--output-result",
    action="store",
    dest="output_result",
    default=RESULT_PATH,
    help="Output the result data here (txt)",
)

parser.add_argument(
    "-ps", "--print-scheme", action="store_true", dest="stdout_scheme", default=False
)
parser.add_argument(
    "-pr", "--print-result", action="store_true", dest="stdout_result", default=False
)

parser.add_argument(
    "-mp", "--multi-process", action="store_true", dest="multi_process", default=False
)

parser.add_argument(
    "-sp", "--single-process", action="store_true", dest="single_process", default=False
)

parser.add_argument(
    "-in",
    "--input",
    action="store",
    dest="input",
    help="Path to the pdf file",
    default=PDF_PATH,
)


def n_clusters(iterable, n=2):
    return list(map(list, zip(*[iter(iterable)] * n)))


""" Later
class IPageType(ABC):
    @abstractmethod
    def __init__():
        pass
    
    @abstractmethod
    def get_header(self):
        pass
    
    """

cache = {}


class PTScheme:
    def __init__(self, schemePage: Page):
        self.schemePage = schemePage
        self.schemeText = schemePage.extract_text_simple()

        r""" Older version (Works on newer scheme headers)
            SCHEME\sOF\sEXAMINATIONS\n
            Prg\.\sCode:\s+(?P<prgCode>\d+)\s+
            Programme:\s+(?P<programme>.*?)\s+
            SchemeID:\s+(?P<schemeID>\d+)\s+
            Sem\.\/Annual:\s+(?P<sem>.*?)\s+
            Institution\sCode:\s+(?P<instCode>\d+)\s+
            Institution:\s+(?P<instName>.*?)\n
        """

        r""" Samples (extracted with extract_text_simple()):
        
        (SCHEME OF EXAMINATIONS)\nScheme of Programme Code: 027     Programme Name: BACHELOR OF TECHNOLOGY (COMPUTER SCIENCE AND ENGINEERING)      SchemeID: 190272016001     Sem./Year: 06 SEMESTER\nInstitution Code: 115     Institution: BHARATI VIDYAPEETH COLLEGE OF ENGINEERING\n

        SCHEME OF EXAMINATIONS\nPrg. Code: 027      Programme: BACHELOR OF TECHNOLOGY (COMPUTER SCIENCE AND ENGINEERING)      SchemeID: 190272021001      Sem./Annual: THIRD SEMESTER\nInstitution Code: 115      Institution: BHARATI VIDYAPEETH COLLEGE OF ENGINEERING\n
        """

        r"""
        How did I write this regex?
        God knows. I don't remember. I just wrote it and it worked.
        Also, \n is a literal n followed by a slash, not a newline.
        Regexer with PCRE treats it as a newline (so use \\n there),
        but python's raw strings treats it as a literal n followed by a slash,
        which is what we want here.
        """

        self.pattern = re.compile(
            r"""
            \(?SCHEME\sOF\sEXAMINATIONS\)?\n
            (?:Scheme\sof\s)?(?:Prg|Programme)\.?\sCode:\s*(?P<prgCode>\d+)\s{2,}
            Programme(?:\sName)?:\s*(?P<programme>.*?)\s{2,}
            SchemeID:\s*(?P<schemeID>\d+)\s{2,}
            Sem\.\/(?:Annual|Year):\s*(?P<sem>.*?)\n
            Institution\sCode:\s*\'?(?P<instCode>\d+)\'?\s{2,}
            Institution:\s*(?P<instName>.*?)\n
        """,
            re.VERBOSE,
        )

    def get_scheme_header(self):
        assert self.is_valid2()
        try:
            """
            Structure of the scheme header(jsonified):
                {
                    'prgCode',
                    'programme',
                    'schemeID',
                    'sem',
                    'instCode',
                    'instName'
                }
            """

            scheme = self.pattern.search(self.schemeText).groupdict()
            modifiedScheme = {**scheme}
            modifiedScheme["sem"] = semHeaderMap[modifiedScheme["sem"]]
            modifiedScheme["institutes"] = [
                {
                    "instCode": modifiedScheme.pop("instCode", None),
                    "instName": modifiedScheme.pop("instName", None),
                }
            ]
            # Modify scheme header here
            return modifiedScheme
        except AttributeError:
            console.print("Failed to get scheme header", style="bold red")
            return None

    def get_scheme_table(self):
        assert self.is_valid2()
        return self.schemePage.extract_table()

    def parse_scheme_table(self):
        header = self.get_scheme_header()
        table = self.schemePage.extract_table()
        # Modify scheme json
        scheme = {**header} | {"subjects": {}}
        """
        Structure of the scheme table (columns):
            'S. No.',
            'PaperID',
            'Paper Code',
            'Paper Name',
            'Credit',
            'Type',
            'Exam',
            'Mode',
            'Kind',
            'Minor',
            'Major',
            'Max. Marks',
            'Pass Marks'
        """
        # Paper Code acts as the primary key / indentifier here, since the paperIDs may carry a prefixed zero sometimes

        if (
            table[0][-1] != "Pass Marks"
            and table[0][-1] == "Max. Marks"
            and table[0][0] != "S. No."
        ):
            # Add a column for S. No. if it's not there, and add a column for Pass Marks if it's not there
            # This is a hacky fix for the table cutting off the first column and the last column
            # Assume, the pass marks is 40 for all subjects

            for row in table:
                row.insert(0, None)
                row.append("40")

        for row in table[1:]:
            scheme["subjects"][row[2]] = {
                "paperID": row[1],
                "paperName": row[3],
                "credits": row[4],
                "type": row[5],
                "exam": row[6],
                "mode": row[7],
                "kind": row[8],
                "minor": row[9],
                "major": row[10],
                "maxMarks": row[11],
                "passMarks": row[12],
            }
        return scheme

    def get_scheme_pretty(self):
        table = self.get_scheme()
        print(pd.DataFrame(table))

    def is_valid(self):
        return self.get_scheme_header() is not None

    def is_valid2(self):
        return self.schemeText.find("SCHEME OF EXAMINATIONS") != -1


class PTResult:
    def __init__(self, page: Page):
        self.page = page
        self.text = page.extract_text_simple()

        r""" Older version (Works on newer result headers)
        Programme\sCode:\s+(?P<prgCode>\d+)\s+
        Programme\sName:\s+(?P<programme>.*?)\s+
        Sem\.\/Year\/EU:\s+(?P<sem>.*?)\s+
        Batch:\s+(?P<batch>\d+)\s+
        Examination:\s+(?P<exam>.*?)\s+
        Result\sDeclared\sDate\s*:\s*(?P<resultDate>.*?)\s+
        """

        r"""
        Samples (extracted with extract_text_simple()):
            Older header:
                Result of Programme Code: 049     Programme Name: BACHELOR OF TECHNOLOGY (ELECTRICAL & ELECTRONICS ENGINEERING)     Sem./Year: 06 SEMESTER     Batch: 2020     Examination: RECHECKING REGULAR July, 2023\n
            Newer header:
                Programme Code: 027      Programme Name: BACHELOR OF TECHNOLOGY (COMPUTER SCIENCE AND ENGINEERING)      Sem./Year/EU: THIRD SEMESTER      Batch: 2021      Examination: REAPPEAR DEC, 2023    Result Declared Date :08-FEB-24\n
        """

        # Works well on newer as well as older headers
        self.pattern = re.compile(
            r"""
            Programme\sCode:\s+(?P<prgCode>\d+)\s{2,}
            Programme\sName:\s+(?P<programme>.*?)\s{2,}
            Sem\.\/Year(?:\/EU)?:\s+(?P<sem>.*?)\s{2,}
            Batch:\s*(?P<batch>\d+)\s{2,}
            Examination:\s*(?P<exam>.*?)(?:\s{2,}|\n)
            (?:Result\sDeclared\sDate\s*:\s*(?P<resultDate>.*?)\n)?
        """,
            re.VERBOSE,
        )

    def get_result_header(self):
        try:
            result = self.pattern.search(self.text).groupdict()
            result["sem"] = semHeaderMap[result["sem"]]

            # The following part tries to parse the result date,
            # and update the cache with a valid result date if there isn't one
            # if it fails, it tries to use the last parsed result date
            # if that fails too, it removes the result date from the header

            if result["resultDate"] is not None:
                try:
                    result["resultDate"] = datetime.strptime(
                        result["resultDate"], "%d-%b-%y"
                    )
                    if "resultDate" not in cache:
                        cache["resultDate"] = result["resultDate"]
                except ValueError:
                    result["resultDate"] = cache.get("resultDate")
                    if result["resultDate"] is None:
                        result.pop("resultDate")
                    # console.print(
                    #     "Failed to parse result date", style="bold red"
                    # )
            else:
                result.pop("resultDate")
            return result
        except AttributeError:
            return None

    def get_result_table(self):
        assert self.is_valid()
        return self.page.extract_table()

    @staticmethod
    def parse_student_details(text: str):
        pattern = re.compile(
            (
                r"(?P<enrollment>\d+)\n(?P<name>.*?)\nSID:\s*(?P<sid>\d+)\nScheme"
                r"ID:\s*(?P<schemeID>\d+)"
            ),
            re.DOTALL,
        )
        try:
            return re.search(pattern, text).groupdict()
        except AttributeError:
            console.print("\nFailed to parse student details", style="bold red")
            return None

    def parse_result_table(self):
        # Retrieves institute info from table's first row not the page header

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "explicit_vertical_lines": [],
            "explicit_horizontal_lines": [],
            "snap_tolerance": 3,
            "snap_x_tolerance": 3,
            "snap_y_tolerance": 8,
            "join_tolerance": 3,
            "join_x_tolerance": 3,
            "join_y_tolerance": 15,
            "edge_min_length": 3,
            "min_words_vertical": 3,
            "min_words_horizontal": 1,
            "intersection_tolerance": 3,
            "intersection_x_tolerance": 3,
            "intersection_y_tolerance": 3,
            "text_tolerance": 3,
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
        }

        pattern = re.compile(
            r"Institution\sCode:\s*(?P<instCode>\d+)\s*Institution:\s*(?P<instName>.*)"
        )

        extracted_table = self.page.extract_table(table_settings)

        # if extracted_table[0][0] != "S. No." and
        # special_case = False

        try:
            instInfo = re.search(pattern, extracted_table[0][2]).groupdict()
            instInfo["instCode"] = int(instInfo["instCode"])
        except AttributeError:
            # console.print(f"Table header: {extracted_table[0]}", style="bold red")
            console.print(
                "\nFailed to get institute code from result table. Is this a result page?",
                style="bold red",
            )

            # special_case = True

            # console.print(
            #     "Attempting to parse the table in a special way", style="bold yellow"
            # )

            # Do I hate myself for writing this? Yes.
            # I shall never write code like this again.

            # Alternative method to get institute info
            """
            try:
                extracted_table = self.page.extract_tables()[1]
                instInfo = re.search(pattern, extracted_table[0][2]).groupdict()
                instInfo["instCode"] = int(instInfo["instCode"])
                print("Special case worked")
            except AttributeError:
                return None
            if "instInfo" not in locals():
                console.print("Failed to get institute info", style="bold red")
                instInfo = {"instCode": None, "instName": None}
                return None
            """

        # here we go again, duck tape and bubblegum

        """if special_case:
            for i, j in enumerate(extracted_table):
                if self.parse_student_details(j[1]):
                    extracted_table = self.page.extract_table()[i:]
                    break
            table = n_clusters(extracted_table, 3)
        else:"""


# WHAT THE FUCK ->

        table = n_clusters(extracted_table[1:], 3)
        result = []
        for row in table:
            row[0] = list(filter(lambda x: x is not None and x != "", row[0]))
            # i = \d+\(\d\) sometimes
            try:
                # row[0] = [row[0][0]] + [i.split()[0] for i in row[0][1:]]
                # print(row[0][1:])
                # (.*?)\n?\s*\(\d\)
                row[0] = [row[0][0]] + [
                    re.match(r"^(.*?)(?:\n\s*)?(?:\(\d+\))?\s*$", i)[1] for i in row[0][1:]
                ]
                row[2] = [None] + list(filter(lambda x: x is not None, row[2]))
                row[0][0] = self.parse_student_details(row[0][0]) | {
                    "institute": instInfo
                }
            except IndexError or TypeError:
                continue
            result.append(list(zip(row[0], n_clusters(row[1]), row[2])))
        return result

    def parse_result_table_to_json(self, stdout: bool = False):
        studentResults = []
        header = self.get_result_header()
        if "resultDate" in header.keys():
            header["resultDate"] = header["resultDate"].isoformat()
        table = self.parse_result_table()
        if table is None:
            return []
        """
        Grading for subject[2]:
            90-100: O
            75-89: A+
            65-74: A
            55-64: B+
            50-54: B
            45-49: C
            40-44: P
            0-39/ABS: F
        """
        for student in table:
            try:
                result = {
                    **student[0][0],
                    "batch": header["batch"],
                    "prgCode": header["prgCode"],
                    "programme": header["programme"],
                    "subjects": {
                        subject[0]: {
                            "internal": subject[1][0],
                            "external": subject[1][1],
                            "total": re.match(
                                r"(\d+|ABS|CAN)?.?\s*\(?(?:.{1,2})?\)?.?", subject[2]
                            )[1],
                            # "total": subject[2].split()[0],
                            # "totalGrade": subject[2].split()[1].strip("()"),
                            "totalGrade": re.match(
                                r"(?:\d+|ABS|CAN)?.?\s*\(?(.{1,2})\)?.?", subject[2]
                            )[1].strip("()"),
                        }
                        for subject in student[1:]
                    },
                    "resultHeader": header,
                }
            except TypeError:
                continue
            studentResults.append(result)
            if stdout:
                rprint(result, end="\r")
        return studentResults

    def get_result_pretty(self):
        table = self.get_result()
        print(pd.DataFrame(table))

    def is_valid(self):
        return self.get_result_header() is not None

    # TODO: Better validity check needed


class enumPageType(StrEnum):
    SCHEME = "SCHEME"
    RESULT = "RESULT"
    UNKNOWN = "UNKNOWN"


class PageType:
    def __init__(self, page: Page):
        self.page = page
        self.ptype = self.get_page_type()

    def get_page_type(self):
        if PTScheme(self.page).is_valid2():
            return enumPageType.SCHEME
        elif PTResult(self.page).is_valid():
            return enumPageType.RESULT
        else:
            return enumPageType.UNKNOWN


class Parser:
    def __init__(self, pages):
        self.pages = pages

    def parse(
        self,
        result_path: str = RESULT_PATH,
        scheme_path: str = SCHEME_PATH,
        stdout_scheme: bool = False,
        stdout_result: bool = False,
        write_to_file: bool = True,
    ):
        schemes = dict()
        studentResults = []
        repeatedSchemeCount = 0
        task = progress.add_task("Parsing", total=len(self.pages))
        with progress:
            for page in self.pages:
                pt = PageType(page)
                rprint("Parsing Page: ", page.page_number, end="\r", flush=True)
                if pt.ptype == enumPageType.SCHEME:
                    scheme = PTScheme(page)
                    header = scheme.get_scheme_header()
                    parsed_scheme_table = scheme.parse_scheme_table()
                    if header["schemeID"] not in schemes:
                        schemes[header["schemeID"]] = parsed_scheme_table
                    else:
                        if (
                            header["institutes"][0]
                            not in schemes[header["schemeID"]]["institutes"]
                        ):
                            schemes[header["schemeID"]]["institutes"].append(
                                header["institutes"][0]
                            )
                        repeatedSchemeCount += 1

                        # Still append the subjects
                        schemes[header["schemeID"]].update(
                            {
                                "subjects": {
                                    **schemes[header["schemeID"]]["subjects"],
                                    **parsed_scheme_table["subjects"],
                                }
                            }
                        )

                        if stdout_scheme:
                            rprint("Repeated Scheme: ", header["schemeID"])
                            rprint(schemes[header["schemeID"]])
                # elif pt.ptype == enumPageType.RESULT:
                #     # result = PTResult(page)
                #     pass
                elif pt.ptype == enumPageType.RESULT:
                    ptresult = PTResult(page).parse_result_table_to_json(
                        stdout=stdout_result
                    )
                    studentResults.extend(ptresult)

                else:
                    rprint("Unknown Page Type: ", pt.ptype)

                # Fix for memory leak
                page.flush_cache()
                progress.update(
                    task,
                    advance=1,
                    description=f"[bold blue]Paring Page:[/] {page.page_number}",
                )

        progress.update(task, completed=True, visible=False)

        if write_to_file:

            # with open(result_path, "w") as f:
            #     f.write("Length: " + str(len(studentResults)) + "\n\n")
            #     for result in studentResults:
            #         f.write(json.dumps(result, indent=4) + "\n\n")

            with open(result_path, "w") as f:
                console.print("\nLength Student Jsons: " + str(len(studentResults)))
                f.write(json.dumps(studentResults, indent=4))

            with open(scheme_path, "w") as f:
                console.print("Length Scheme Jsons: " + str(len(schemes)))
                console.print(
                    "Repeated Scheme Count: " + str(repeatedSchemeCount) + "\n\n"
                )
                # for _, value in schemes.items():
                #     f.write(json.dumps(value, indent=4) + "\n\n")
                f.write(json.dumps(list(schemes.values()), indent=4))

        return list(schemes.values()), studentResults, repeatedSchemeCount

    @staticmethod
    def parse_page(
        page_chunk,
        pdf_path,
        shared_repeatedSchemeCount,
        shared_result,
        shared_scheme,
        stdout_scheme,
        stdout_result,
    ):
        schemes = []
        studentResults = []
        repeatedSchemeCount = 0
        with pdfplumber.open(pdf_path) as pdf:
            pages = [pdf.pages[page_num - 1] for page_num in page_chunk]
            """with progress:
                for page in pages:
                    pt = PageType(page)
                    rprint("Parsing Page: ", page.page_number, end="\r", flush=True)
                    if pt.ptype == enumPageType.SCHEME:
                        scheme = PTScheme(page)
                        header = scheme.get_scheme_header()
                        parsed_scheme_table = scheme.parse_scheme_table()
                        if header["schemeID"] not in schemes:
                            schemes[header["schemeID"]] = parsed_scheme_table
                        else:
                            schemes[header["schemeID"]]["institutes"].append(
                                header["institutes"][0]
                            )
                            repeatedSchemeCount += 1
                            if stdout_scheme:
                                rprint("Repeated Scheme: ", header["schemeID"])
                                rprint(schemes[header["schemeID"]])
                    # elif pt.ptype == enumPageType.RESULT:
                    #     # result = PTResult(page)
                    #     pass
                    else:
                        ptresult = PTResult(page).parse_result_table_to_json(
                            stdout=stdout_result
                        )
                        studentResults.extend(ptresult)

                    # Fix for memory leak
                    page.flush_cache()"""

            data = Parser(pages).parse(
                write_to_file=False,
                stdout_result=stdout_result,
                stdout_scheme=stdout_scheme,
            )
            schemes.extend(data[0])
            studentResults.extend(data[1])
            repeatedSchemeCount += data[2]

        shared_repeatedSchemeCount.value += repeatedSchemeCount
        shared_result.extend(studentResults)
        shared_scheme.extend(schemes)


class ParserSenpai:
    @staticmethod
    def multiprocessing_parser(
        pdf_path: str = PDF_PATH,
        stdout_result: bool = False,
        stdout_scheme: bool = False,
        result_path: str = RESULT_PATH,
        scheme_path: str = SCHEME_PATH,
        write_to_file: bool = True,
    ):
        with Manager() as manager:
            shared_result = manager.list()
            shared_scheme = manager.list()
            shared_repeatedSchemeCount = manager.Value(int, 0)

            with pdfplumber.open(pdf_path) as pdf:
                page_range = range(0, len(pdf.pages))

            # tested with a few runs, 100 pages per worker seems to be the sweet spot
            pages_per_worker = 100
            page_chunks = [
                list(group)
                for _, group in groupby(page_range, lambda x: x // pages_per_worker)
            ]

            with Pool(processes=4) as pool:
                pool.starmap(
                    Parser.parse_page,
                    [
                        (
                            page_chunk,
                            pdf_path,
                            shared_repeatedSchemeCount,
                            shared_result,
                            shared_scheme,
                            stdout_scheme,
                            stdout_result,
                        )
                        for page_chunk in page_chunks
                    ],
                )

            final_result = list(shared_result)
            final_scheme = list(shared_scheme)
            final_repeatedSchemeCount = shared_repeatedSchemeCount.value

        if write_to_file:

            # with open(result_path, "w") as f:
            #     f.write("Length: " + str(len(studentResults)) + "\n\n")
            #     for result in studentResults:
            #         f.write(json.dumps(result, indent=4) + "\n\n")

            with open(result_path, "w") as f:
                console.print(
                    "\nLength Student Jsons: " + str(len(final_result)), style="bold blue"
                )
                f.write(json.dumps(final_result, indent=4))

            with open(scheme_path, "w") as f:
                console.print(
                    "Length Scheme Jsons: " + str(len(final_scheme)), style="bold blue"
                )
                console.print(
                    "Repeated Scheme Count: " + str(final_repeatedSchemeCount) + "\n\n"
                )
                # for _, value in schemes.items():
                #     f.write(json.dumps(value, indent=4) + "\n\n")
                f.write(json.dumps(final_scheme, indent=4))

        return final_scheme, final_result, final_repeatedSchemeCount

    """
        Single Process Parser
        If write_to_file is True, the result and scheme will be written to the respective files
        If stdout_scheme or stdout_result is True, the parsed data will be printed to the console
        If write_to_file is False, the parsed data will be returned as a tuple (scheme, result),
        and result_path and scheme_path will be ignored
    """

    @staticmethod
    def single_process_parser(
        pdf_path: str = PDF_PATH,
        stdout_scheme: bool = False,
        stdout_result: bool = False,
        result_path: str = RESULT_PATH,
        scheme_path: str = SCHEME_PATH,
        write_to_file: bool = False,
        offset: int = 0,
    ):

        console.print(f"Parsing [bold blue]{pdf_path}[/]")

        with pdfplumber.open(pdf_path) as pdf:
            return Parser(pdf.pages[offset:]).parse(
                result_path=result_path,
                scheme_path=scheme_path,
                stdout_scheme=stdout_scheme,
                stdout_result=stdout_result,
                write_to_file=write_to_file,
            )


if __name__ == "__main__":
    from time import time

    try:
        start = time()
        args = parser.parse_args()

        if args.single_process:
            ParserSenpai.single_process_parser(
                args.input,
                args.stdout_scheme,
                args.stdout_result,
                args.output_result,
                args.output_scheme,
                write_to_file=True,
                offset=0,
            )

        if args.multi_process:
            ParserSenpai.multiprocessing_parser(
                args.input,
                args.stdout_result,
                args.stdout_scheme,
                args.output_result,
                args.output_scheme,
                write_to_file=True,
            )

        print("Time Elapsed: ", time() - start)

    except KeyboardInterrupt:
        print("Keyboard Interrupt")
