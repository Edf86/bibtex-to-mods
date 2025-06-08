# app.py  –  BibTeX → MODS XML  (bibtexparser ≥ 2.0)

import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import uuid
import bibtexparser

# ----------------------------------------------------------------------
# bibtexparser ≥ 2.0 : build a parser with middlewares
# ----------------------------------------------------------------------
from bibtexparser import Parser
from bibtexparser.middlewares import ParagraphMiddleware, AuthorMiddleware

def build_parser() -> Parser:
    """
    Returns a bibtexparser.Parser that:
      • turns multi-line values into single paragraphs
      • splits `author` into Person objects (has first_names / last_names)
    """
    p = Parser()
    p.add_middleware(ParagraphMiddleware())
    p.add_middleware(AuthorMiddleware())
    return p

BIB_PARSER = build_parser()

# ----------------------------------------------------------------------
# XML helpers
# ----------------------------------------------------------------------
MODS_NS = "http://www.loc.gov/mods/v3"
ET.register_namespace("", MODS_NS)

def prettify(elem: ET.Element) -> str:
    return minidom.parseString(ET.tostring(elem, encoding="utf-8")).toprettyxml(indent="  ")

def add_text(parent, tag, text, **attrib):
    """Add <tag>text</tag> if *text* is truthy, return the element or None."""
    if text:
        el = ET.SubElement(parent, f"{{{MODS_NS}}}{tag}", attrib)
        el.text = text
        return el
    return None

# ----------------------------------------------------------------------
# Author handling
# ----------------------------------------------------------------------
def split_name(person_or_str):
    """
    Accepts either a bibtexparser Person OR a plain string and returns
    (given, family).
    """
    # Person object (AuthorMiddleware produced it)
    if hasattr(person_or_str, "first_names"):
        given  = " ".join(person_or_str.first_names)
        family = " ".join(person_or_str.last_names)
        return given, family

    # Fallback: naive split of "Family, Given" or "Given Family"
    s = person_or_str.strip()
    if "," in s:
        family, given = [p.strip() for p in s.split(",", 1)]
    else:
        parts  = s.split()
        family = parts[-1]
        given  = " ".join(parts[:-1])
    return given, family

# ----------------------------------------------------------------------
# BibTeX entry  →  <mods>
# ----------------------------------------------------------------------
def entry_to_mods(entry) -> ET.Element:
    mods = ET.Element(f"{{{MODS_NS}}}mods", version="3.3")

    # Title ----------------------------------------------------------------
    if "title" in entry:
        ti = ET.SubElement(mods, f"{{{MODS_NS}}}titleInfo")
        add_text(ti, "title", entry["title"])

    # Authors --------------------------------------------------------------
    for person in entry.get("author", []):
        given, family = split_name(person)
        n = ET.SubElement(mods, f"{{{MODS_NS}}}name", type="personal")
        add_text(n, "namePart", given, type="given")
        add_text(n, "namePart", family, type="family")

        role = ET.SubElement(n, f"{{{MODS_NS}}}role")
        add_text(role, "roleTerm", "aut", authority="marcrelator", type="code")
        add_text(role, "roleTerm", "author", type="text")

    # Language -------------------------------------------------------------
    lang = entry.get("language") or entry.get("langid")
    if lang:
        lang_el = ET.SubElement(mods, f"{{{MODS_NS}}}language")
        add_text(lang_el, "languageTerm", lang, authority="iso639-2b", type="code")

    # Subjects -------------------------------------------------------------
    for kw in entry.get("keywords", "").replace(";", ",").split(","):
        if kw.strip():
            subj = ET.SubElement(mods, f"{{{MODS_NS}}}subject")
            add_text(subj, "topic", kw.strip())

    # Identifiers ----------------------------------------------------------
    for typ in ("doi", "isbn", "issn", "hdl", "isi"):
        if typ in entry:
            add_text(mods, "identifier", entry[typ], type=typ)

    # Abstract -------------------------------------------------------------
    add_text(mods, "abstract", entry.get("abstract"))

    # Origin info (date) ---------------------------------------------------
    if "year" in entry:
        oi = ET.SubElement(mods, f"{{{MODS_NS}}}originInfo")
        add_text(oi, "dateIssued", entry["year"])

    # Host container (journal / booktitle / publisher) ---------------------
    host_title = entry.get("journal") or entry.get("booktitle") or entry.get("publisher")
    if host_title:
        host = ET.SubElement(mods, f"{{{MODS_NS}}}relatedItem", type="host")
        ti = ET.SubElement(host, f"{{{MODS_NS}}}titleInfo")
        add_text(ti, "title", host_title)

        if "issn" in entry:
            add_text(host, "identifier", entry["issn"], type="issn")

        part = ET.SubElement(host, f"{{{MODS_NS}}}part")
        add_text(part, "detail", entry.get("volume"), type="volume")
        add_text(part, "detail", entry.get("number"), type="issue")

        if "pages" in entry:
            start, *end = entry["pages"].replace("--", "-").split("-")
            ext = ET.SubElement(part, f"{{{MODS_NS}}}extent", unit="page")
            add_text(ext, "start", start)
            add_text(ext, "end", end[0] if end else start)

        add_text(part, "date", entry.get("year"))

    # Publication status (optional) ---------------------------------------
    add_text(mods, "note", entry.get("status"), type="publicationStatus")

    # Location / URL -------------------------------------------------------
    if "url" in entry:
        loc = ET.SubElement(mods, f"{{{MODS_NS}}}location")
        add_text(loc, "url", entry["url"])

    # Minimal recordInfo ---------------------------------------------------
    ri = ET.SubElement(mods, f"{{{MODS_NS}}}recordInfo")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    add_text(ri, "recordContentSource", "streamlit-converter")
    add_text(ri, "recordCreationDate", now, encoding="iso8601")
    add_text(ri, "recordChangeDate", now, encoding="iso8601")
    add_text(ri, "recordIdentifier", str(uuid.uuid4()))

    # Resource type --------------------------------------------------------
    add_text(mods, "typeOfResource", "text")

    return mods

# ----------------------------------------------------------------------
# Complete BibTeX → <modsCollection>
# ----------------------------------------------------------------------
def bibtex_to_mods(xml_input: str) -> str:
    bib_db = BIB_PARSER.parse_string(xml_input)

    collection = ET.Element(f"{{{MODS_NS}}}modsCollection")
    for entry in bib_db.entries:
        collection.append(entry_to_mods(entry))

    return prettify(collection)

# ----------------------------------------------------------------------
# Streamlit UI
# ----------------------------------------------------------------------
st.set_page_config(page_title="BibTeX → MODS XML")
st.title("BibTeX naar MODS XML converter")

uploads = st.file_uploader(
    "Upload één of meerdere BibTeX-bestanden (.bib)",
    type="bib",
    accept_multiple_files=True,
)

if uploads:
    all_xml = []
    for f in uploads:
        xml_out = bibtex_to_mods(f.read().decode("utf-8"))
        all_xml.append(xml_out)

    final_xml = "\n".join(all_xml)

    st.download_button(
        "Download MODS XML",
        data=final_xml,
        file_name="mods_output.xml",
        mime="application/xml",
    )
    st.code(final_xml, language="xml")

