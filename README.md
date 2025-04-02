# ParserSenpai

A powerful PDF parser for extracting structured data from GGGSIPU (Guru Gobind Singh Indraprastha University) result PDFs.

![ParserSenpai](https://img.shields.io/badge/Parser-Senpai-blue)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-GPL3-green)

## Overview
ParserSenpai addresses the challenge of extracting structured data from GGGSIPU result PDFs, which are typically difficult to parse due to their complex layout and inconsistent formatting. Using advanced regex pattern matching and PDF extraction techniques, the tool identifies and extracts both scheme information (course structures, credit systems) and student results (marks, grades) from these documents.

The parser handles various edge cases including different PDF layouts across semesters, inconsistent table structures, and variations in result declaration formats. It efficiently processes both single-page and multi-page documents, transforming raw PDF data into clean, structured JSON that can be easily integrated with databases, analysis tools, or educational management systems.

This project serves as the backbone for ipusenpai.in, although we have an ETL (Extract, Transform, Load) pipeline that handles the data extraction and transformation. ParserSenpai is designed to be a standalone tool that can be used independently of the website.

Created by: [martian0x80](https://github.com/martian0x80)

## Features

- Extract detailed scheme information from PDFs
- Extract student results including internal/external marks and grades
- Support for both single-process and multi-process parsing
- Export data to JSON files
- Handle various PDF formats and layouts
- Memory-efficient processing of large PDF files

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/martian0x80/ParserSenpai.git
   cd ParserSenpai
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

### Dependencies

- pdfplumber: For PDF extraction
- pandas: For pretty printing
- rich: For beautiful console output

## Usage

### Basic Usage

```bash
python ParserSenpai.py -in "path/to/your/result.pdf" -sp
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `-in`, `--input` | Path to the input PDF file | `RESULT_BTECH7_DEC2023.pdf` |
| `-os`, `--output-scheme` | Output path for scheme data (JSON) | `scheme.txt` |
| `-or`, `--output-result` | Output path for result data (JSON) | `result.txt` |
| `-ps`, `--print-scheme` | Print scheme data to console | `False` |
| `-pr`, `--print-result` | Print result data to console | `False` |
| `-sp`, `--single-process` | Use single process parsing | `False` |
| `-mp`, `--multi-process` | Use multi-process parsing (faster for large PDFs) | `False` |

### Examples

#### Single Process Parsing

```bash
python ParserSenpai.py -in "RESULT_BTECH7_DEC2023.pdf" -sp -os "scheme_output.json" -or "result_output.json"
```

#### Multi Process Parsing (Recommended for Large PDFs)

```bash
python ParserSenpai.py -in "RESULT_BTECH7_DEC2023.pdf" -mp -os "scheme_output.json" -or "result_output.json"
```

#### Print Results to Console

```bash
python ParserSenpai.py -in "RESULT_BTECH7_DEC2023.pdf" -sp -pr
```

### Sample Files

The `samples/` directory contains example exports generated from sample PDFs:
- `sample_result.json`: Example result data extracted from the sample PDF
- `sample_scheme.json`: Example scheme data extracted from the sample PDF

You can reproduce these samples or create your own using:

```bash
python ParserSenpai.py -in "samples/sample_result.pdf" -sp -os "samples/sample_scheme.json" -or "samples/sample_result.json"
```

These sample files are helpful for understanding the output format and structure without having to process a complete PDF.

### Using as a Library

You can also import ParserSenpai in your Python code:

```python
from ParserSenpai import ParserSenpai

# For single process parsing
schemes, results, _ = ParserSenpai.single_process_parser(
    pdf_path="path/to/your/result.pdf",
    write_to_file=True,
    result_path="output_results.json",
    scheme_path="output_schemes.json"
)

# For multi-process parsing
schemes, results, _ = ParserSenpai.multiprocessing_parser(
    pdf_path="path/to/your/result.pdf",
    write_to_file=True,
    result_path="output_results.json",
    scheme_path="output_schemes.json"
)
```

## Output Format

### Scheme Output

The scheme output contains information about courses, credits, and evaluation patterns:

```json
[
  {
    "prgCode": "027",
    "programme": "BACHELOR OF TECHNOLOGY (COMPUTER SCIENCE AND ENGINEERING)",
    "schemeID": "190272021001",
    "sem": 3,
    "institutes": [
      {
        "instCode": 115,
        "instName": "BHARATI VIDYAPEETH COLLEGE OF ENGINEERING"
      }
    ],
    "subjects": {
      "ETCS301": {
        "paperID": "2021301",
        "paperName": "DATA STRUCTURES",
        "credits": "4",
        "type": "THEORY",
        "exam": "END SEM",
        "mode": "CWE",
        "kind": "COMPULSORY",
        "minor": "25",
        "major": "75",
        "maxMarks": "100",
        "passMarks": "40"
      },
      // Additional subjects...
    }
  }
]
```

### Result Output

The result output contains student details and their performance:

```json
[
    {
        "enrollment": "51455302718",
        "name": "SANCHIT KASHYAP",
        "sid": "190000106416",
        "schemeID": "190272016001",
        "institute": {
            "instCode": 553,
            "instName": "BM INSTITUTE OF ENGINEERING & TECHNOLOGY"
        },
        "batch": "2018",
        "prgCode": "027",
        "programme": "BACHELOR OF TECHNOLOGY (COMPUTER SCIENCE AND ENGINEERING)",
        "subjects": {
            "ETMA101": {
                "internal": "20",
                "external": "ABS",
                "total": "ABS",
                "totalGrade": "F"
            }
        },
        "resultHeader": {
            "prgCode": "027",
            "programme": "BACHELOR OF TECHNOLOGY (COMPUTER SCIENCE AND ENGINEERING)",
            "sem": 1,
            "batch": "2018",
            "exam": "REAPPEAR DEC, 2023",
            "resultDate": "2024-02-22T00:00:00"
        }
    },
    // Additional students...
]
```

## Performance

Performance varies based on the size of the PDF and the hardware, parser-senpai is cpu-intensive and can take advantage of multiple cores. The multi-process version is significantly faster for larger PDFs.
- **Single Process**: Slower, but simpler and easier to debug
- **Multi Process**: Faster, especially for larger PDFs, but requires more resources

The multi-process version divides the PDF into chunks of 100 pages per worker and processes them in parallel.

## Limitations

- Currently optimized for GGGSIPU result PDFs
- Some PDF formats may require adjustments to the regular expressions
- The parser assumes a specific structure of the result and scheme pages

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the GPLv3 License - see the LICENSE file for details.
