
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def extract_text_from_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path, strict=True)
        text_parts = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text_parts.append(page_text)

        return "\n".join(text_parts).strip()

    except (PdfReadError, OSError, ValueError) as error:
        raise ValueError("Could not read this PDF file.") from error

def validate_extracted_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("Extracted PDF text must be a string.")

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "No readable text was found in this PDF."
        )

    return cleaned_text
