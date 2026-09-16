#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3CATEPG - Generador d'EPG per als canals de 3Cat
Extreu la graella de programació de les URLs de 3Cat
i genera un fitxer XMLTV amb tots els canals.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from lxml import etree

# --- Configuració ---
CHANNELS = {
    "tv3": {
        "url": "https://www.3cat.cat/tv3/programacio/canal-tv3/",
        "name": "TV3",
    },
    "c33": {
        "url": "https://www.3cat.cat/tv3/programacio/canal-33/",
        "name": "33",
    },
    "3catinfo": {
        "url": "https://www.3cat.cat/tv3/programacio/canal-324/",
        "name": "3CatInfo",
    },
    "esport3": {
        "url": "https://www.3cat.cat/tv3/programacio/canal-esport3/",
        "name": "Esport3",
    },
    "super3": {
        "url": "https://www.3cat.cat/tv3/programacio/canal-super3/",
        "name": "Super3",
    },
    "tv3cat": {
        "url": "https://www.3cat.cat/tv3/programacio/canal-tv3cat/",
        "name": "TV3Cat",
    },
}

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
XML_PATH = OUTPUT_DIR / "epg.xml"
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


def build_channel_element(tv: etree._Element, channel_id: str, name: str) -> None:
    """Afegeix un element <channel> al document XMLTV."""
    ch_elem = etree.SubElement(tv, "channel", id=channel_id)
    display = etree.SubElement(ch_elem, "display-name")
    display.text = name


def build_programme_elements(tv: etree._Element, channel_id: str,
                             programmes: list[dict]) -> None:
    """Afegeix els elements <programme> d'un canal al document XMLTV."""
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
            "channel": channel_id,
        })
        t = etree.SubElement(p, "title", lang="ca")
        t.text = prog["title"]
        if prog["desc"]:
            d = etree.SubElement(p, "desc", lang="ca")
            d.text = prog["desc"]
        if prog["image"]:
            etree.SubElement(p, "icon", src=prog["image"])


def main():
    tv = etree.Element("tv", attrib={"generator-info-name": "3CATEPG"})

    total_programes = 0
    canals_ok = 0

    for channel_id, info in CHANNELS.items():
        print(f"Processant {info['name']} ({channel_id})...")
        try:
            resp = requests.get(info["url"], timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Error descarregant {info['url']}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        programmes = extract_programmes(soup)
        print(f"  Trobats {len(programmes)} programes.")

        if not programmes:
            print(f"  Avís: cap programa trobat per a {info['name']}, s'omet.")
            continue

        build_channel_element(tv, channel_id, info["name"])
        build_programme_elements(tv, channel_id, programmes)

        total_programes += len(programmes)
        canals_ok += 1

    if canals_ok == 0:
        print("Error: no s'ha pogut processar cap canal.")
        sys.exit(1)

    xml_bytes = etree.tostring(tv, pretty_print=True, encoding="UTF-8",
                               xml_declaration=True)
    XML_PATH.write_text(xml_bytes.decode("utf-8"), encoding="utf-8")
    print(f"\nEscrit {XML_PATH}")
    print(f"Canals processats: {canals_ok}")
    print(f"Total de programes: {total_programes}")


if __name__ == "__main__":
    main()
