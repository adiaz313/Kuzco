"""Retrieval helpers copied from local-analyst; standard library only."""
from collections import Counter
from pathlib import Path
import math
import re
import zipfile
from defusedxml import ElementTree as ET


def split_chunks(text, size=120, overlap=25):
    """Group sentences within sections, carrying a short tail into the next chunk.

    Plain text has no Word styles, so a short standalone line without sentence
    punctuation is treated as a heading. This is a heuristic, not a Word parser.
    """
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be positive and overlap smaller than size.")
    chunks, sentences = [], []
    heading = "Document"

    def emit():
        if sentences:
            chunks.append(heading + "\n" + " ".join(sentences))

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        is_heading = (len(line.split()) <= 8 and line[0].isupper() and
                      not re.search(r'[.!?:;,“”"\t]', line))
        if is_heading:
            emit()
            sentences = []  # Never carry overlap from an unrelated section.
            heading = line
            continue
        for sentence in re.split(r'(?<=[.!?])\s+', line):
            words = sentence.split()
            # Rare oversized sentences fall back to word boundaries.
            for start in range(0, len(words), size):
                part = " ".join(words[start:start + size])
                if sentences and len(" ".join(sentences).split()) + len(part.split()) > size:
                    emit()
                    tail = []
                    for previous in reversed(sentences):
                        if len(" ".join([previous] + tail).split()) > overlap:
                            break
                        tail.insert(0, previous)
                    if not tail:
                        tail = [" ".join(" ".join(sentences).split()[-overlap:])] if overlap else []
                    sentences = tail if len(" ".join(tail).split()) + len(part.split()) <= size else []
                sentences.append(part)
    emit()
    return chunks

def bm25_scores(chunks, question):
    """BM25 rewards shared rare words, with length and repetition adjustments."""
    stop = set("a an the is are was were be this that these those what which who why how does do did for of to in on and or it its".split())
    def tokens(text):
        return [word for word in re.findall(r"[^\W_]+", text.lower()) if word not in stop]
    counts = [Counter(tokens(chunk)) for chunk in chunks]
    lengths = [sum(count.values()) for count in counts]
    average = sum(lengths) / len(lengths) if lengths else 0
    scores = [0.0] * len(chunks)
    if not average:
        return scores
    k1, b = 1.5, 0.75  # Standard BM25 defaults, not fitted to this document.
    for term in set(tokens(question)):
        frequency = sum(term in count for count in counts)
        idf = math.log(1 + (len(chunks) - frequency + 0.5) / (frequency + 0.5))
        for i, count in enumerate(counts):
            tf = count[term]
            scores[i] += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lengths[i] / average))
    return scores

def extract_docx(path):
    """A DOCX is a ZIP archive; its main text lives in word/document.xml."""
    path = Path(path).expanduser()
    if path.suffix.lower() != ".docx":
        raise ValueError("Please supply a .docx file, not .doc or PDF.")
    with zipfile.ZipFile(path) as archive:
        # Bound decompression before reading. Pictures are never opened.
        if archive.getinfo("word/document.xml").file_size > 5_000_000:
            raise ValueError("Document XML is too large for this simple reader.")
        root = ET.fromstring(archive.read("word/document.xml"), forbid_dtd=True)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def read(element):
        # Keep paragraphs and table cells in document order, including hyperlinks.
        if element.tag in (ns + "del", ns + "moveFrom"):
            return ""  # Exclude text marked as deleted by tracked changes.
        if element.tag == ns + "t":
            return element.text or ""
        if element.tag == ns + "tab":
            return "\t"
        if element.tag in (ns + "br", ns + "cr"):
            return "\n"
        text = "".join(read(child) for child in element)
        if element.tag == ns + "tc":
            return text.rstrip() + "\t"
        if element.tag in (ns + "p", ns + "tr"):
            return text.rstrip() + "\n"
        return text

    body = root.find(ns + "body")
    if body is None:
        raise ValueError("The file has no Word document body.")
    text = read(body).strip()
    if not text:
        raise ValueError("No readable document text found. Images are not OCR'd.")
    return text
