import os
from PyPDF2 import PdfReader
from docx import Document


def extract_document(path):

    extension = os.path.splitext(path)[1].lower()

    if extension == ".pdf":

        reader = PdfReader(path)

        text = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text.append(page_text)

        return "\n".join(text)

    elif extension == ".docx":

        document = Document(path)

        text = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)

        return "\n".join(text)

    else:
        raise ValueError("Unsupported document format")


def generate_summary(text):

    if not text:
        return "No text could be extracted."

    # Temporary simple summary.
    # We will connect the AI engine later.
    words = text.split()

    if len(words) <= 100:
        return text

    return " ".join(words[:100]) + "..."