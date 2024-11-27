from docx import Document
import fitz
import io
import re
import spacy
import pymupdf4llm
from langchain_text_splitters import MarkdownHeaderTextSplitter


class ReadingFunctions:
    def __init__(self):
        self.nlp = spacy.load(
            "en_core_web_sm",
            disable=[
                "tagger",
                "attribute_ruler",
                "lemmatizer",
                "ner",
                "textcat",
                "custom",
            ],
        )
        self.max_file_size_mb = 50
        self.headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            self.headers_to_split_on, strip_headers=False, return_each_line=True
        )

    def read_file(self, file_bytes: bytes, file_name: str):
        """Read and process file content from bytes"""
        file_size_mb = self._get_file_size(file_bytes=file_bytes)
        file_type = file_name.split(".")[-1].lower()

        if file_size_mb > self.max_file_size_mb:
            raise ValueError(f"File size exceeds {self.max_file_size_mb}MB limit")

        try:
            if file_type == "pdf":
                return self._process_pdf(file_bytes=file_bytes)
            elif file_type == "docx":
                return self._process_docx(file_bytes=file_bytes)
            elif file_type in ["txt", "rtf"]:
                return self._process_txt(file_bytes=file_bytes)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            raise ValueError(f"Error processing {file_name}: {str(e)}")

    def _process_pdf(self, file_bytes: bytes):
        pdf_data = {"sentences": [], "page_number": [], "is_header": [], "is_table": []}
        pdf_file = io.BytesIO(file_bytes)
        with fitz.open(stream=pdf_file, filetype="pdf") as pdf:
            # Process each page
            markdown_pages = pymupdf4llm.to_markdown(
                pdf, page_chunks=True, show_progress=False
            )
            for i, page in enumerate(markdown_pages):
                splits = self.markdown_splitter.split_text(page["text"])
                for split in splits:
                    if not len(split.page_content) > 5 or re.match(
                        r"^[^\w]*$", split.page_content
                    ):
                        continue
                    elif (
                        split.metadata and split.page_content[0] == "#"
                    ):  # Header detection
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(True)
                        pdf_data["is_table"].append(False)
                        pdf_data["page_number"].append(i + 1)
                    elif (split.page_content[0] == "*" and split.page_content[-1] == '*' and (re.match(r"(\*{2,})(\d+(?:\.\d+)*)\s*(\*{2,})?(.*)$",split.page_content) or re.match(r"(\*{1,3})?([A-Z][a-zA-Z\s\-]+)(\*{1,3})?$",split.page_content))
                    ): # Sub-Header and Header variant detection
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(True)
                        pdf_data["is_table"].append(False)
                        pdf_data["page_number"].append(i+1)
                    elif (
                        split.page_content[0] == "|" and split.page_content[-1] == "|"
                    ):  # Table detection
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(False)
                        pdf_data["is_table"].append(True)
                        pdf_data["page_number"].append(i + 1)
                    else:
                        pdf_data["sentences"].append(split.page_content)
                        pdf_data["is_header"].append(False)
                        pdf_data["is_table"].append(False)
                        pdf_data["page_number"].append(i + 1)
        return pdf_data

    def _process_docx(self, file_bytes: bytes):
        docx_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
        }

        docx_file = io.BytesIO(file_bytes)
        doc = Document(docx_file)

        current_length = 0
        chars_per_page = 2000
        current_page = 1

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            if current_length + len(text) > chars_per_page:
                current_page += 1
                current_length = 0

            paragraph_style = paragraph.style.name
            if ("Heading" in paragraph_style) or ("Title" in paragraph_style):
                docx_data["sentences"].append(self._clean_text(text=text))
                docx_data["page_number"].append(current_page)
                docx_data["is_header"].append(True)
                current_length += len(text)
                continue

            paragraph_sentences = self._process_text(text=text)
            docx_data["sentences"].extend(paragraph_sentences)
            docx_data["page_number"].extend([current_page] * len(paragraph_sentences))
            docx_data["is_header"].extend([False] * len(paragraph_sentences))
            current_length += len(text)

        return docx_data

    def _process_txt(self, file_bytes: bytes):
        text_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
        }
        text = file_bytes.decode("utf-8", errors="ignore")
        valid_sentences = self._process_text(text=text)
        text_data["sentences"].extend(valid_sentences)
        text_data["page_number"].extend([1] * len(valid_sentences))
        text_data["is_header"].extend([False] * len(valid_sentences))

        return text_data

    def _process_text(self, text):
        docs = self.nlp(text)
        sentences = [sent.text.replace("\n", " ").strip() for sent in docs.sents]
        return [sentence for sentence in sentences if len(sentence) > 15]

    def _get_file_size(self, file_bytes: bytes) -> None:
        return len(file_bytes) / (1024 * 1024)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"(\b\w+)\s*\n\s*(\w+\b)", r"\1 \2", text)
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
        text = re.sub(r"[,()]\s*\n\s*(\w+)", r" \1", text)
        text = re.sub(r"(\b\w+)\s*-\s*(\w+\b)", r"\1 \2", text)
        text = re.sub(r"(\w+)\s*[-–]\s*(\w+)", r"\1\2", text)
        text = re.sub(
            r"(?:[\s!\"#$%&\'()*+,\-.:;<=>?@\[\\\]^_`{|}~]+)(?!\w)", r" ", text
        )
        text = text.replace("\n", " ").strip()
        return " ".join(text.split())
