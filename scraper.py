#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3CATEPG - Generador d'EPG per a TV3Cat
Extreu la graella de programació de https://www.3cat.cat/tv3/programacio/canal-tv3cat/
i genera un fitxer XMLTV.
"""

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from lxml import etree

# --- Configuració ---
URL = "https://www.3cat.cat/tv3/programacio/canal-tv3cat/"
CHANNEL_ID = "tv3cat"
CHANNEL_NAME = "TV3Cat"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
XML_PATH = OUTPUT_DIR / "tv3cat.xml"
TZ_OFFSET = "+0200"  # CEST (estiu). A l'hivern caldria canviar a +0100.

# --- Utilitats ---

def parse_time_to_xmltv(dt: datetime) -> str:
    """Converteix un datetime a format XMLTV: YYYYMMDDHHMMSS +HHMM"""
    return dt.strftime("%Y%m%d%H%M%S") + " " + TZ_OFFSET


def extract_programmes(soup: BeautifulSoup) -> list[dict]:
    """Extreu la llista de programes del HTML."""
    programmes = []
    # Cada programa és un <li class="graellacatchup_programa__...">
    for li in soup.select("li[class*=graellacatchup_programa]"):
        time_tag = li.find("time")
        if not time_tag:
            continue
        dt_str = time_tag.get("datetime")
        if not dt_str:
            continue
        try:
            start_dt = datetime.fromisoformat(dt_str)
        except ValueError:
            continue

        # Títol
        title_tag = li.select_one("p[class*=graellacatchup_titol] a")
        title = title_tag.get_text(strip=True) if title_tag else "Sense títol"

        # Descripció (a vegades buida)
        desc_tag = li.select_one("p[class*=graellacatchup_capitol]")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        # Imatge (opcional)
        img_tag = li.select_one("img")
        image_url = img_tag.get("src") if img_tag else ""

        programmes.append({
            "start": start_dt,
            "title": title,
            "desc": desc,
            "image": image_url,
        })
    return programmes


def build_xmltv(programmes: list[dict]) -> str:
    """Genera el document XMLTV."""
    tv = etree.Element("tv", attrib={"generator-info-name": "3CATEPG"})

    # Canal
    channel = etree.SubElement(tv, "channel", id=CHANNEL_ID)
    display = etree.SubElement(channel, "display-name")
    display.text = CHANNEL_NAME

    # Ordena per hora d'inici
    programmes.sort(key=lambda p: p["start"])

    for i, prog in enumerate(programmes):
        start = prog["start"]
        # El stop és l'inici del següent programa, o +1h si és l'últim
        if i + 1 < len(programmes):
            stop = programmes[i + 1]["start"]
        else:
            stop = start + timedelta(hours=1)

        p = etree.SubElement(tv, "programme", attrib={
            "start": parse_time_to_xmltv(start),
            "stop": parse_time_to_xmltv(stop),
            "channel": CHANNEL_ID,
        })
        t = etree.SubElement(p, "title", lang="ca")
        t.text = prog["title"]
        if prog["desc"]:
            d = etree.SubElement(p, "desc", lang="ca")
            d.text = prog["desc"]
        if prog["image"]:
            icon = etree.SubElement(p, "icon", src=prog["image"])

    # Pretty print
    xml_bytes = etree.tostring(tv, pretty_print=True, encoding="UTF-8",
                               xml_declaration=True)
    return xml_bytes.decode("utf-8")


def main():
    print(f"Descarregant {URL}...")
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    programmes = extract_programmes(soup)
    print(f"Trobats {len(programmes)} programes.")

    if not programmes:
        print("Avís: no s'han trobat programes. Revisa el selector.")
        sys.exit(1)

    xml_str = build_xmltv(programmes)
    XML_PATH.write_text(xml_str, encoding="utf-8")
    print(f"Escrit {XML_PATH}")


if __name__ == "__main__":
    main()
