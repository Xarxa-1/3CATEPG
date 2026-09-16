# 3CATEPG

Generador d'EPG (Electronic Program Guide) per als canals de **3Cat** en format XMLTV.

## Què fa?

- Descarrega la graella de programació de cada canal de 3Cat.
- Extreu títol, descripció, hora d'inici i imatge de cada programa.
- Genera un únic fitxer XMLTV estàndard a `output/epg.xml` amb tots els canals.

## Canals inclosos

| ID | Nom | URL |
|---|---|---|
| `tv3` | TV3 | https://www.3cat.cat/tv3/programacio/canal-tv3/ |
| `c33` | 33 | https://www.3cat.cat/tv3/programacio/canal-33/ |
| `3catinfo` | 3CatInfo | https://www.3cat.cat/tv3/programacio/canal-324/ |
| `esport3` | Esport3 | https://www.3cat.cat/tv3/programacio/canal-esport3/ |
| `super3` | Super3 | https://www.3cat.cat/tv3/programacio/canal-super3/ |
| `tv3cat` | TV3Cat | https://www.3cat.cat/tv3/programacio/canal-tv3cat/ |

## Ús local

```bash
pip install -r requirements.txt
python scraper.py
