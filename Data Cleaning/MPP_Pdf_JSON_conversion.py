from PyPDF2 import PdfReader

PDF_PATH = "fsman04a.pdf"  # path to your downloaded file
OUT_JSON = "MPP_testing.json"

reader = PdfReader(PDF_PATH)
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n"

print(text[:10000])
