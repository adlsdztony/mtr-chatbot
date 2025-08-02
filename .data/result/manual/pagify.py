import pymupdf
import argparse

"""
The purpose of this file is to extract each page of PDF file as an image, which will later be used for reference system.
"""

# INFO: add cli arguments
parser = argparse.ArgumentParser()
parser.add_argument("-f", type=str, default="manual_origin.pdf")
args = parser.parse_args()

# INFO: open pdf file
pdf_file = pymupdf.open(args.f)

# extract each page
for page_id, page in enumerate(pdf_file): # type: ignore
    pix = page.get_pixmap()
    pix.save(f"pages/page_{page_id + 1}.png")