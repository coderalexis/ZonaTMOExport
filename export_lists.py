#!/usr/bin/env python3
"""Exporta listas de ZonaTMO/LectorManga a HTML en una sola ejecución."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode

import browser_cookie3
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_BASE_URL = "https://lectormanga.nakamasweb.com/profile/follow"
KNOWN_PROFILE_LISTS = [
    ("Siguiendo", "https://lectormanga.nakamasweb.com/profile/follow"),
    ("Pendiente", "https://lectormanga.nakamasweb.com/profile/pending"),
    ("Viendo", "https://lectormanga.nakamasweb.com/profile/watch"),
    ("Favorito", "https://lectormanga.nakamasweb.com/profile/wish"),
    ("Tengo", "https://lectormanga.nakamasweb.com/profile/have"),
    ("Abandonado", "https://lectormanga.nakamasweb.com/profile/abandoned"),
]


@dataclass
class MangaItem:
    title: str
    link: str
    image_url: str


@dataclass
class MangaList:
    title: str
    url: str


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <style>
    body {{ background:#121212; color:#fff; font-family:Arial,sans-serif; margin:0; }}
    .topnav {{ background:#1e1e1e; padding:12px 16px; font-size:20px; font-weight:700; text-align:center; }}
    .container {{ padding:16px; display:flex; justify-content:center; }}
    table {{ width:min(1100px,95%); border-collapse:collapse; background:#222; }}
    th, td {{ border:1px solid #444; padding:10px; text-align:left; }}
    th {{ background:#333; }}
    td:first-child {{ width:80px; text-align:center; }}
    img {{ width:60px; height:80px; object-fit:cover; border-radius:4px; }}
    a {{ color:#1e90ff; }}
  </style>
</head>
<body>
  <div class=\"topnav\">{title}</div>
  <div class=\"container\">
    <table>
      <thead><tr><th>Imagen</th><th>Título</th></tr></thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return clean or "lista"


def update_page_param(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def parse_list_links(base_html: str, base_url: str) -> list[MangaList]:
    soup = BeautifulSoup(base_html, "html.parser")
    found: list[MangaList] = []
    seen: set[str] = set()

    for link in soup.select(".element-header-bar-element a[href]"):
        href = urljoin(base_url, link.get("href", "").strip())
        if not href or href in seen:
            continue
        title = link.get_text(" ", strip=True) or "Mi Lista"
        seen.add(href)
        found.append(MangaList(title=title, url=href))

    if found:
        return found

    # fallback para páginas de una sola lista (por ejemplo lector.manganakamas)
    title = soup.select_one("h2.text-primary")
    found.append(
        MangaList(
            title=(title.get_text(strip=True) if title else "Mi Lista"),
            url=base_url,
        )
    )
    return found


def known_lists_for_url(base_url: str) -> list[MangaList]:
    host = (urlparse(base_url).hostname or "").lower()
    if host == "lectormanga.nakamasweb.com":
        return [MangaList(title=title, url=url) for title, url in KNOWN_PROFILE_LISTS]
    return []


def parse_items(html: str, page_url: str) -> list[MangaItem]:
    soup = BeautifulSoup(html, "html.parser")

    zonatmo_items = soup.select(".element.proyect-item")
    if zonatmo_items:
        return parse_zonatmo_items(zonatmo_items, page_url)

    lector_items = soup.select(".card")
    if lector_items:
        return parse_lectormanga_items(lector_items, page_url)

    return []


def parse_zonatmo_items(items, page_url: str) -> list[MangaItem]:
    output: list[MangaItem] = []
    for item in items:
        title = (
            item.select_one(".thumbnail-title h4.text-truncate")
            and item.select_one(".thumbnail-title h4.text-truncate").get("title", "").strip()
        ) or "Sin título"

        link_tag = item.select_one("a[href]")
        link = urljoin(page_url, link_tag.get("href", "").strip()) if link_tag else "#"

        image_url = "Sin imagen"
        style_tag = item.select_one("style")
        if style_tag and style_tag.text:
            match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style_tag.text)
            if match:
                image_url = match.group(1).strip()

        output.append(MangaItem(title=title, link=link, image_url=image_url))
    return output


def parse_lectormanga_items(items, page_url: str) -> list[MangaItem]:
    output: list[MangaItem] = []
    for item in items:
        title_link = item.select_one(".card-header a")
        body_link = item.select_one(".card-body a[href]")
        img = item.select_one(".card-body img")

        title = (title_link.get("title") or title_link.get_text(strip=True)) if title_link else "Sin título"
        link = urljoin(page_url, body_link.get("href", "").strip()) if body_link else "#"
        image_url = urljoin(page_url, img.get("src", "").strip()) if img else "Sin imagen"

        output.append(MangaItem(title=title.strip(), link=link, image_url=image_url))
    return output


def fetch_paginated_items(session: requests.Session, list_url: str, max_pages: int) -> list[MangaItem]:
    all_items: list[MangaItem] = []

    for page in range(1, max_pages + 1):
        page_url = update_page_param(list_url, page)
        resp = session.get(page_url, timeout=30)
        if not resp.ok:
            print(f"  [!] Página {page} devolvió {resp.status_code}. Se detiene esta lista.")
            break

        items = parse_items(resp.text, page_url)
        if not items:
            print(f"  [i] Sin elementos en página {page}. Fin de la lista.")
            break

        all_items.extend(items)
        print(f"  [+] Página {page}: {len(items)} elementos")

    return all_items


def render_html(title: str, items: Iterable[MangaItem]) -> str:
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td><img src=\"{item.image_url}\" alt=\"{item.title}\" /></td>"
            f"<td><a href=\"{item.link}\" target=\"_blank\" rel=\"noopener noreferrer\">{item.title}</a></td>"
            "</tr>"
        )
    return HTML_TEMPLATE.format(title=title, rows="\n".join(rows))


def load_browser_cookie_jar(browser: str, domain: str):
    loaders = {
        "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
        "brave": browser_cookie3.brave,
        "opera": browser_cookie3.opera,
    }

    loader = loaders.get(browser)
    if not loader:
        raise ValueError(f"Navegador no soportado: {browser}")
    return loader(domain_name=domain)


def build_session(cookie_header: str, browser: str, domain: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    if cookie_header:
        session.headers.update({"Cookie": cookie_header})
        return session

    if browser:
        jar = load_browser_cookie_jar(browser, domain)
        session.cookies.update(jar)

    return session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Exporta todas tus listas de ZonaTMO/LectorManga en un solo comando. "
            "Necesitas pasar cookies de sesión del navegador para acceder al perfil privado."
        )
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"URL principal del perfil/lista (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--cookie", default="", help="Cookie completa en formato de header: 'a=b; c=d'")
    parser.add_argument(
        "--browser",
        default="",
        choices=["chrome", "chromium", "edge", "firefox", "brave", "opera"],
        help="Lee cookies automáticamente del navegador (evita copiar cookie manual).",
    )
    parser.add_argument(
        "--cookie-domain",
        default="",
        help="Dominio para filtrar cookies del navegador. Default: dominio de --base-url.",
    )
    parser.add_argument("--output-dir", default="exports", help="Carpeta donde se guardan los .html")
    parser.add_argument("--max-pages", default=300, type=int, help="Límite de páginas por lista para evitar loops")
    return parser.parse_args()


def interactive_auth_menu(args: argparse.Namespace) -> argparse.Namespace:
    if args.browser or args.cookie:
        return args

    options = [
        ("chrome", "Usar cookies de Chrome"),
        ("firefox", "Usar cookies de Firefox"),
        ("edge", "Usar cookies de Edge"),
        ("brave", "Usar cookies de Brave"),
        ("opera", "Usar cookies de Opera"),
        ("cookie", "Pegar cookie manual"),
        ("none", "Continuar sin autenticación"),
    ]

    print("\nNo indicaste --browser ni --cookie.")
    print("Selecciona cómo quieres autenticarte:")
    for idx, (_, label) in enumerate(options, start=1):
        print(f"  {idx}. {label}")

    while True:
        selection = input("Opción [1-7]: ").strip()
        if not selection.isdigit():
            print("Entrada inválida. Escribe un número.")
            continue
        selected_index = int(selection)
        if not 1 <= selected_index <= len(options):
            print("Número fuera de rango.")
            continue
        key = options[selected_index - 1][0]
        if key == "cookie":
            args.cookie = getpass("Pega la cookie completa (no se mostrará): ").strip()
        elif key != "none":
            args.browser = key
        return args


def main() -> int:
    args = interactive_auth_menu(parse_args())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_base = urlparse(args.base_url)
    cookie_domain = args.cookie_domain or parsed_base.hostname or ""
    session = build_session(args.cookie, args.browser, cookie_domain)

    print(f"[*] Cargando base: {args.base_url}")
    resp = session.get(args.base_url, timeout=30)
    if not resp.ok:
        print(f"[x] No se pudo abrir la URL base ({resp.status_code}).")
        return 1

    manga_lists = known_lists_for_url(args.base_url)
    if not manga_lists:
        manga_lists = parse_list_links(resp.text, args.base_url)
    print(f"[*] Listas detectadas: {len(manga_lists)}")

    total_items = 0
    for manga_list in manga_lists:
        print(f"\n=== {manga_list.title} ===")
        print(f"URL: {manga_list.url}")
        items = fetch_paginated_items(session, manga_list.url, args.max_pages)
        total_items += len(items)

        filename = sanitize_filename(manga_list.title) + ".html"
        destination = output_dir / filename
        destination.write_text(render_html(manga_list.title, items), encoding="utf-8")
        print(f"[✓] Exportado: {destination} ({len(items)} elementos)")

    print(f"\n[✓] Terminado. Archivos en: {output_dir.resolve()} | Elementos totales: {total_items}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
