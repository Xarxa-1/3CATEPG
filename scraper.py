#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3CATEPG - Generador d'EPG per als canals de 3Cat
Extreu la graella de programació de les URLs de 3Cat
i genera un fitxer XMLTV amb tots els canals.

Aquesta versió llegeix el JSON __NEXT_DATA__ incrustat a la pàgina,
que conté els camps estructurats (titol, entradeta, data_emissio, etc.)
i per tant és molt més robusta que fer scraping de classes CSS.
"""

import json
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
        "url": "https://www.3cat.cat/tv3/programacio/canal-3catinfo-tv/",
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


def parse_iso_datetime(value: str) -> datetime | None:
    """Parseja una data ISO de 3Cat. Accepta formats amb o sense segons."""
    if not value:
        return None
    # Normalitza: 3Cat de vegades envia "2026-09-16T06:00:00" i de vegades
    # "2026-09-16 06:00:00"
    value = value.replace(" ", "T")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Intenta només amb data i hora sense segons
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def extract_programmes_from_next_data(soup: BeautifulSoup) -> list[dict]:
    """
    Extreu els programes del JSON __NEXT_DATA__ incrustat a la pàgina.
    Retorna una llista de diccionaris amb start, stop, title, desc, image.
    """
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return []

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return []

    # Navega per l'estructura de Next.js buscant el mòdul GraellaCatchup
    items = _find_graella_items(data)
    if not items:
        return []

    programmes = []
    for item in items:
        start = parse_iso_datetime(item.get("data_emissio", ""))
        if not start:
            continue

        title = (item.get("titol_tdt") or item.get("titol") or "Sense títol").strip()
        desc = (item.get("entradeta") or "").strip()
        image = (item.get("url_imatge_destacat") or "").strip()

        programmes.append({
            "start": start,
            "title": title,
            "desc": desc,
            "image": image,
            "durada": item.get("durada"),  # opcional
        })

    return programmes


def _find_graella_items(node) -> list[dict]:
    """
    Recorre recursivament l'estructura de __NEXT_DATA__ buscant el mòdul
    GraellaCatchup i retorna la llista d'items que conté.
    """
    if isinstance(node, dict):
        # Detecta el mòdul GraellaCatchup
        if node.get("moduleName") == "GraellaCatchup":
            final = node.get("finalProps") or node
            items = final.get("items")
            if isinstance(items, list):
                return items

        # Cerca en profunditat
        for value in node.values():
            result = _find_graella_items(value)
            if result:
                return result

    elif isinstance(node, list):
        for item in node:
            result = _find_graella_items(item)
            if result:
                return result

    return []


def extract_programmes_from_html(soup: BeautifulSoup) -> list[dict]:
    """
    Fallback: extreu els programes del HTML si el JSON no està disponible.
    """
    programmes = []
    for li in soup.select("li[class*=graellacatchup_programa]"):
        time_tag = li.find("time")
        if not time_tag:
            continue
        dt_str = time_tag.get("datetime")
        start_dt = parse_iso_datetime(dt_str) if dt_str else None
        if not start_dt:
            continue

        title_tag = li.select_one("p[class*=graellacatchup_titol] a")
        title = title_tag.get_text(strip=True) if title_tag else "Sense títol"

        # Descripció: busca el paràgraf que segueix el títol
        desc = ""
        for p in li.find_all("p"):
            classes = " ".join(p.get("class", []))
            if "titol" in classes or "hora" in classes:
                continue
            text = p.get_text(strip=True)
            if text and len(text) > 20:
                desc = text
                break

        img_tag = li.select_one("img")
        image_url = img_tag.get("src") if img_tag else ""

        programmes.append({
            "start": start_dt,
            "title": title,
            "desc": desc,
            "image": image_url,
        })
    return programmes


def extract_programmes(soup: BeautifulSoup) -> list[dict]:
    """Intenta primer el JSON __NEXT_DATA__ i, si falla, el HTML."""
    programmes = extract_programmes_from_next_data(soup)
    if programmes:
        return programmes
    return extract_programmes_from_html(soup)


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
        if i + 1 < len(programmes):
            stop = programmes[i + 1]["start"]
        else:
            stop = start + timedelta(hours=1)

        p = etree.SubElement(tv, "programme", attrib={
            "start": parse_time_to_xmltv(start),
            "stop": parse_time_to_xmltv(stop),
            "channel": channel_id,
        })

        # Títol
        t = etree.SubElement(p, "title", lang="ca")
        t.text = prog["title"]

        # Descripció (entradeta)
        if prog.get("desc"):
            d = etree.SubElement(p, "desc", lang="ca")
            d.text = prog["desc"]

        # Imatge
        if prog.get("image"):
            etree.SubElement(p, "icon", src=prog["image"])


def main():
    tv = etree.Element("tv", attrib={"generator-info-name": "3CATEPG"})

    total_programes = 0
    canals_ok = 0
    programes_amb_desc = 0

    for channel_id, info in CHANNELS.items():
        print(f"Processant {info['name']} ({channel_id})...")
        try:
            resp = requests.get(info["url"], timeout=30,
                                headers={"User-Agent": "Mozilla/5.0 (3CATEPG)"})
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

        # Comprova quantes descripcions s'han trobat
        amb_desc = sum(1 for p in programmes if p.get("desc"))
        print(f"  Amb descripció: {amb_desc}/{len(programmes)}")

        build_channel_element(tv, channel_id, info["name"])
        build_programme_elements(tv, channel_id, programmes)

        total_programes += len(programmes)
        programes_amb_desc += amb_desc
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
    print(f"Programes amb descripció: {programes_amb_desc}")


if __name__ == "__main__":
    main()
