from docx import Document
import fitz
import io
import re
import spacy


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
        pdf_data = {
            "sentences": [],
            "page_number": [],
            "is_header": [],
        }
        pdf_file = io.BytesIO(file_bytes)
        with fitz.open(stream=pdf_file, filetype="pdf") as pdf:
            # Process each page
            for page_num in range(len(pdf)):
                page = pdf.load_page(page_num)
                blocks = page.get_text("dict")["blocks"]
                text_blocks = [block for block in blocks if block.get("type") == 0]
                # Process each block
                for text_block in text_blocks:
                    if "lines" not in text_block:
                        continue

                    block_sentences, block_headers = self._process_pdf_block(text_block)
                    pdf_data["sentences"].extend(block_sentences)
                    pdf_data["page_number"].extend(
                        [page_num + 1] * len(block_sentences)
                    )
                    pdf_data["is_header"].extend(block_headers)

        return pdf_data

    def _process_pdf_block(self, block: dict):
        """Process individual PDF block"""
        block_sentences = []
        block_headers = []

        if len(block["lines"]) >= 1 and len(block["lines"]) < 5:
            # Process potential headers
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if self._is_header(span, text):
                        block_sentences.append(text)
                        block_headers.append(True)
                    elif len(text) > 15 and not self._is_separator(text):
                        block_sentences.append(text)
                        block_headers.append(False)
        else:
            # Process regular text
            text = " ".join(
                span["text"] for line in block["lines"] for span in line["spans"]
            )
            clean_text = self._clean_text(text)
            if len(clean_text) > 15:
                block_sentences.append(clean_text)
                block_headers.append(False)

        return block_sentences, block_headers

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

    def _is_header(self, span: dict, text: str) -> bool:
        return (
            span["size"] > 3
            and any(style in span["font"] for style in ["Medi", "Bold", "B"])
            and len(text) > 3
            and text[0].isalpha()
            and not self._is_separator(text)
        )

    def _is_separator(self, text: str) -> bool:
        return bool(re.search(r"^[^\w\s]+$|^[_]+$", text))

    def _extract_pdf_header(self, first_page):
        file_header = ""
        blocks = first_page.get_text("dict")["blocks"]
        text_blocks = [block for block in blocks if block.get("type") == 0]

        for block in text_blocks[:3]:  # Look at first 3 blocks only
            if "lines" in block and 1 <= len(block["lines"]) < 4:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if self._is_header(span, span["text"]):
                            file_header += f" {span['text']}"

        return file_header
