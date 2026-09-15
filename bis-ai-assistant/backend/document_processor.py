import os
import io

from pypdf import PdfReader
from docx import Document
from PIL import Image
import pytesseract


# If tesseract is not detected automatically,
# uncomment the following line and change the path.

# pytesseract.pytesseract.tesseract_cmd = (
#     r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# )


def extract_pdf_text(path):
    """
    Extract normal text from PDF.
    """

    reader = PdfReader(path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text.strip()


def extract_docx_text(path):
    """
    Extract text from DOCX.
    """

    document = Document(path)

    text = ""

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text.strip()


def ocr_image(path):
    """
    OCR an image file.
    """

    image = Image.open(path)

    text = pytesseract.image_to_string(image)

    return text.strip()


def process_document(path):
    """
    Main document-processing function.

    Returns:

    {
        "text": extracted text,
        "ocr_used": True/False,
        "file_type": ...
    }
    """

    extension = os.path.splitext(path)[1].lower()

    # -------------------------
    # PDF
    # -------------------------

    if extension == ".pdf":

        text = extract_pdf_text(path)

        # If PDF has no selectable text,
        # it is probably scanned.
        if len(text.strip()) < 50:

            # For now return a clear status.
            # Full scanned-PDF OCR requires rendering
            # PDF pages to images.

            return {
                "text": text,
                "ocr_used": False,
                "file_type": "PDF",
                "status": "OCR_REQUIRED"
            }

        return {
            "text": text,
            "ocr_used": False,
            "file_type": "PDF",
            "status": "PROCESSED"
        }

    # -------------------------
    # DOCX
    # -------------------------

    elif extension == ".docx":

        text = extract_docx_text(path)

        return {
            "text": text,
            "ocr_used": False,
            "file_type": "DOCX",
            "status": "PROCESSED"
        }

    # -------------------------
    # Images
    # -------------------------

    elif extension in [".png", ".jpg", ".jpeg"]:

        text = ocr_image(path)

        return {
            "text": text,
            "ocr_used": True,
            "file_type": "IMAGE",
            "status": "PROCESSED"
        }

    else:

        raise ValueError(
            "Unsupported file type. "
            "Only PDF, DOCX, PNG, JPG and JPEG are supported."
        )