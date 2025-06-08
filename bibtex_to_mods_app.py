
import streamlit as st
import bibtexparser
import xml.etree.ElementTree as ET
from xml.dom import minidom

st.title("BibTeX naar MODS XML Converter")

uploaded_file = st.file_uploader("Upload een BibTeX-bestand (.bib)", type="bib")

def bibtex_to_mods_string(bibtex_content):
    bib_database = bibtexparser.loads(bibtex_content)

    mods_ns = "http://www.loc.gov/mods/v3"
    ET.register_namespace('', mods_ns)
    mods_collection = ET.Element('{%s}modsCollection' % mods_ns)

    for entry in bib_database.entries:
        mods = ET.SubElement(mods_collection, '{%s}mods' % mods_ns)

        if 'title' in entry:
            title_info = ET.SubElement(mods, '{%s}titleInfo' % mods_ns)
            title = ET.SubElement(title_info, '{%s}title' % mods_ns)
            title.text = entry['title']

        if 'author' in entry:
            authors = [a.strip() for a in entry['author'].replace('\n', ' ').split(' and ')]
            for author in authors:
                name = ET.SubElement(mods, '{%s}name' % mods_ns, type="personal")
                name_part = ET.SubElement(name, '{%s}namePart' % mods_ns)
                name_part.text = author
                role = ET.SubElement(name, '{%s}role' % mods_ns)
                role_term = ET.SubElement(role, '{%s}roleTerm' % mods_ns, type="text")
                role_term.text = "author"

        if 'year' in entry:
            origin_info = ET.SubElement(mods, '{%s}originInfo' % mods_ns)
            date_issued = ET.SubElement(origin_info, '{%s}dateIssued' % mods_ns)
            date_issued.text = entry['year']

        if 'journal' in entry:
            related_item = ET.SubElement(mods, '{%s}relatedItem' % mods_ns, type="host")
            title_info = ET.SubElement(related_item, '{%s}titleInfo' % mods_ns)
            title = ET.SubElement(title_info, '{%s}title' % mods_ns)
            title.text = entry['journal']

        if 'doi' in entry:
            identifier = ET.SubElement(mods, '{%s}identifier' % mods_ns, type="doi")
            identifier.text = entry['doi']

        if 'abstract' in entry:
            abstract = ET.SubElement(mods, '{%s}abstract' % mods_ns)
            abstract.text = entry['abstract']

        genre = ET.SubElement(mods, '{%s}genre' % mods_ns)
        genre.text = entry.get('ENTRYTYPE', 'article')

        resource_type = ET.SubElement(mods, '{%s}typeOfResource' % mods_ns)
        resource_type.text = "text"

    rough_string = ET.tostring(mods_collection, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

if uploaded_file:
    bib_content = uploaded_file.read().decode("utf-8")
    mods_xml = bibtex_to_mods_string(bib_content)
    st.download_button("Download MODS XML", mods_xml, file_name="mods_output.xml", mime="application/xml")
    st.code(mods_xml, language="xml")
