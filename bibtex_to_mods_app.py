import streamlit as st
import bibtexparser
from bibtexparser.customization import author, convert_to_unicode
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import uuid

# ----------------------------------------------------------------------
# Streamlit page
# ----------------------------------------------------------------------
st.set_page_config(page_title="BibTeX → MODS XML")
st.title("BibTeX naar MODS XML converter")

uploaded_files = st.file_uploader(
    "Upload één of meerdere BibTeX-bestanden (.bib)",
    type="bib",
    accept_multiple_files=True,
)

# ----------------------------------------------------------------------
# XML helpers
# ----------------------------------------------------------------------
MODS_NS = "http://www.loc.gov/mods/v3"
ET.register_namespace("", MODS_NS)

def prettify(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")

def add_text(parent, tag, text, **attrib):
    """Add <tag>text</tag> under *parent* when *text* is not empty."""
    if text:
        el = ET.SubElement(parent, f"{{{MODS_NS}}}{tag}", attrib)
        el.text = text
        return el
    return None

def split_name(person):
    """Return (given, family) for a bibtexparser Person object."""
    return " ".join(person.first_names), " ".join(person.last_names)

# ----------------------------------------------------------------------
# One BibTeX entry   →   one <mods>
# ----------------------------------------------------------------------
def entry_to_mods(entry) -> ET.Element:
    mods = ET.Element(f"{{{MODS_NS}}}mods", version="3.3")

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------
    if "title" in entry:
        ti = ET.SubElement(mods, f"{{{MODS_NS}}}titleInfo")
        add_text(ti, "title", entry["title"])

    # ------------------------------------------------------------------
    # Personal names
    # ------------------------------------------------------------------
    for person in entry.get("author_list", []):      # injected later
        given, family = split_name(person)

        n = ET.SubElement(mods, f"{{{MODS_NS}}}name", type="personal")
        add_text(n, "namePart", given, type="given")
        add_text(n, "namePart", family, type="family")

        role = ET.SubElement(n, f"{{{MODS_NS}}}role")
        add_text(role, "roleTerm", "aut", authority="marcrelator", type="code")
        add_text(role, "roleTerm", "author", type="text")

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    lang = entry.get("language") or entry.get("langid")
    if lang:
        lang_el = ET.SubElement(mods, f"{{{MODS_NS}}}language")
        add_text(lang_el, "languageTerm", lang, authority="iso639-2b", type="code")

    # ------------------------------------------------------------------
    # Keywords → subject/topic
    # ------------------------------------------------------------------
    kw_source = entry.get("keywords", "")
    for kw in kw_source.replace(";", ",").split(","):
        if kw.strip():
            subj = ET.SubElement(mods, f"{{{MODS_NS}}}subject")
            add_text(subj, "topic", kw.strip())

    # ------------------------------------------------------------------
    # Identifiers
    # ------------------------------------------------------------------
    for typ in ("doi", "isbn", "issn", "hdl", "isi"):
        if typ in entry:
            add_text(mods, "identifier", entry[typ], type=typ)

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------
    add_text(mods, "abstract", entry.get("abstract"))

    # ------------------------------------------------------------------
    # Origin information (date)
    # ------------------------------------------------------------------
    if "year" in entry:
        oi = ET.SubElement(mods, f"{{{MODS_NS}}}originInfo")
        add_text(oi, "dateIssued", entry["year"])

    # ------------------------------------------------------------------
    # Host container  (journal / booktitle / proceedings)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Publication status  (optional free text)
    # ------------------------------------------------------------------
    add_text(mods, "note", entry.get("status"), type="publicationStatus")

    # ------------------------------------------------------------------
    # Location / URL
    # ------------------------------------------------------------------
    if "url" in entry:
        loc = ET.SubElement(mods, f"{{{MODS_NS}}}location")
        add_text(loc, "url", entry["url"])

    # ------------------------------------------------------------------
    # Minimal recordInfo
    # ------------------------------------------------------------------
    ri = ET.SubElement(mods, f"{{{MODS_NS}}}recordInfo")
    add_text(ri, "recordContentSource", "streamlit-converter")
    now = datetime.utcnow().isoformat() + "Z"
    add_text(ri, "recordCreationDate", now, encoding="iso8601")
    add_text(ri, "recordChangeDate", now, encoding="iso8601")
    add_text(ri, "recordIdentifier", str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # Resource type
    # ------------------------------------------------------------------
    add_text(mods, "typeOfResource", "text")

    return mods

# ----------------------------------------------------------------------
# Complete BibTeX file  →  <modsCollection>
# ----------------------------------------------------------------------
def bibtex_to_mods(bibtex_str: str) -> str:
    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    parser.customization = lambda rec: convert_to_unicode(author(rec))

    bib_db = bibtexparser.loads(bibtex_str, parser=parser)

    for e in bib_db.entries:
        # Keep list of Person objects for cleaner handling later
        e["author_list"] = e.pop("author", [])

    collection = ET.Element(f"{{{MODS_NS}}}modsCollection")
    for entry in bib_db.entries:
        collection.append(entry_to_mods(entry))

    return prettify(collection)

# ----------------------------------------------------------------------
# Run conversion for every uploaded file
# ----------------------------------------------------------------------
if uploaded_files:
    all_xml_strings = []
    for f in uploaded_files:
        xml_str = bibtex_to_mods(f.read().decode("utf-8"))
        all_xml_strings.append(xml_str)

    combined_xml = "\n".join(all_xml_strings)

    st.download_button(
        "Download MODS XML",
        combined_xml,
        file_name="mods_output.xml",
        mime="application/xml",
    )
    st.code(combined_xml, language="xml")
