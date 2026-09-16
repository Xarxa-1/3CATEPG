# 3CATEPG

Generador d'EPG (Electronic Program Guide) per al canal **TV3Cat** de 3Cat.

## Què fa?

- Descarrega la graella de programació de https://www.3cat.cat/tv3/programacio/canal-tv3cat/
- Extreu títol, descripció, hora d'inici i imatge de cada programa.
- Genera un fitxer XMLTV estàndard a `output/tv3cat.xml`.

## Ús local

```bash
pip install -r requirements.txt
python scraper.py
