#!/usr/bin/env python3
"""Exporta listas de ZonaTMO/LectorManga a HTML en una sola ejecución."""

from __future__ import annotations

import argparse
from http.cookiejar import MozillaCookieJar
import random
import re
import time
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

DEFAULT_BASE_URL = "https://lectormanga.nakamasweb.com/profile/follow/true"
KNOWN_PROFILE_LISTS = [
    ("Siguiendo", "https://lectormanga.nakamasweb.com/profile/follow/true"),
    ("Pendiente", "https://lectormanga.nakamasweb.com/profile/pending/true"),
    ("Viendo", "https://lectormanga.nakamasweb.com/profile/watch/true"),
    ("Favorito", "https://lectormanga.nakamasweb.com/profile/wish/true"),
    ("Tengo", "https://lectormanga.nakamasweb.com/profile/have/true"),
    ("Abandonado", "https://lectormanga.nakamasweb.com/profile/abandoned/true"),
]


@dataclass
class MangaItem:
    title: str
    link: str
    image_url: str
    read_chapters: int | None = None
    total_chapters: int | None = None
    progress: float | None = None


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


HTML_TEMPLATE_PROGRESS = """<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <style>
    body {{ background:#121212; color:#fff; font-family:Arial,sans-serif; margin:0; }}
    .topnav {{ background:#1e1e1e; padding:12px 16px; font-size:20px; font-weight:700; text-align:center; }}
    .container {{ padding:16px; display:flex; justify-content:center; }}
    table {{ width:min(1300px,95%); border-collapse:collapse; background:#222; }}
    th, td {{ border:1px solid #444; padding:10px; text-align:center; }}
    th {{ background:#333; }}
    td:first-child {{ width:80px; }}
    td:nth-child(2) {{ text-align:left; }}
    img {{ width:60px; height:80px; object-fit:cover; border-radius:4px; }}
    a {{ color:#1e90ff; }}
    .progress-bar {{ background:#444; border-radius:4px; overflow:hidden; height:20px; }}
    .progress-fill {{ background:#4caf50; height:100%; transition:width .3s; }}
  </style>
</head>
<body>
  <div class=\"topnav\">{title}</div>
  <div class=\"container\">
    <table>
      <thead><tr><th>Imagen</th><th>Título</th><th>Leídos</th><th>Total</th><th>Progreso</th></tr></thead>
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


def fetch_chapter_progress(
    session: requests.Session,
    item: MangaItem,
    *,
    delay_range: tuple[float, float] = (1.0, 3.0),
) -> MangaItem:
    """Visita la página de detalle de un manga y cuenta capítulos leídos/totales."""
    time.sleep(random.uniform(*delay_range))

    try:
        resp = session.get(item.link, timeout=30)
    except requests.RequestException:
        return item

    if resp.status_code == 429:
        print(f"  [!] 429 para {item.title} — omitido")
        return item
    if not resp.ok:
        print(f"  [!] {resp.status_code} para {item.title} — omitido")
        return item

    soup = BeautifulSoup(resp.text, "html.parser")

    # Cada capítulo tiene un span.chapter-viewed-icon con data-chapter único.
    # fa-eye = leído, fa-eye-slash = no leído.
    # Un mismo capítulo puede tener múltiples uploads (scanlators), así que
    # deduplicamos por data-chapter.
    all_chapter_spans = soup.select(".chapter-viewed-icon[data-chapter]")
    seen_chapters: set[str] = set()
    total = 0
    read = 0
    for span in all_chapter_spans:
        ch_id = span.get("data-chapter", "")
        if not ch_id or ch_id in seen_chapters:
            continue
        seen_chapters.add(ch_id)
        total += 1
        if "fa-eye" in span.get("class", []) and "fa-eye-slash" not in span.get("class", []):
            read += 1

    pct = round(read / total * 100, 1) if total > 0 else 0.0

    return MangaItem(
        title=item.title,
        link=item.link,
        image_url=item.image_url,
        read_chapters=read,
        total_chapters=total,
        progress=pct,
    )


def enrich_items_with_progress(
    session: requests.Session,
    items: list[MangaItem],
    *,
    delay_range: tuple[float, float] = (1.0, 3.0),
) -> list[MangaItem]:
    """Enriquece cada manga con datos de progreso de capítulos."""
    enriched: list[MangaItem] = []
    total = len(items)
    for idx, item in enumerate(items, 1):
        print(f"  [{idx}/{total}] Obteniendo progreso: {item.title}")
        enriched.append(fetch_chapter_progress(session, item, delay_range=delay_range))
    return enriched


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


def render_html(title: str, items: Iterable[MangaItem], *, with_progress: bool = False) -> str:
    rows = []
    for item in items:
        row = (
            "<tr>"
            f"<td><img src=\"{item.image_url}\" alt=\"{item.title}\" /></td>"
            f"<td><a href=\"{item.link}\" target=\"_blank\" rel=\"noopener noreferrer\">{item.title}</a></td>"
        )
        if with_progress:
            read = item.read_chapters if item.read_chapters is not None else "—"
            total = item.total_chapters if item.total_chapters is not None else "—"
            pct = item.progress if item.progress is not None else 0
            pct_display = f"{pct}%" if item.progress is not None else "—"
            row += (
                f"<td>{read}</td>"
                f"<td>{total}</td>"
                f"<td><div class=\"progress-bar\"><div class=\"progress-fill\" style=\"width:{pct}%\"></div></div>"
                f"<small>{pct_display}</small></td>"
            )
        row += "</tr>"
        rows.append(row)
    template = HTML_TEMPLATE_PROGRESS if with_progress else HTML_TEMPLATE
    return template.format(title=title, rows="\n".join(rows))


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
    try:
        return loader(domain_name=domain)
    except PermissionError as exc:
        raise RuntimeError(
            "No se pudo leer la base de cookies del navegador por permisos/bloqueo. "
            "Cierra el navegador por completo o usa --cookie / --cookie-file."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "Error al abrir cookies del navegador. "
            "Intenta cerrar el navegador o usar --cookie / --cookie-file."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "No se pudieron descifrar cookies del navegador (DPAPI/MAC). "
            "Esto pasa en algunos perfiles de Brave/Chrome. "
            "Usa --cookie-file (recomendado) o --cookie manual."
        ) from exc


def load_cookie_file(cookie_file: str, domain: str) -> requests.cookies.RequestsCookieJar:
    jar = MozillaCookieJar(cookie_file)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"No existe el archivo de cookies: {cookie_file}") from exc
    except OSError as exc:
        raise RuntimeError(f"No se pudo leer el archivo de cookies: {cookie_file}") from exc

    output = requests.cookies.RequestsCookieJar()
    for cookie in jar:
        if domain and domain not in cookie.domain:
            continue
        output.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
    return output


def build_session(cookie_header: str, browser: str, cookie_file: str, domain: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    if cookie_header:
        session.headers.update({"Cookie": cookie_header})
        return session

    if cookie_file:
        session.cookies.update(load_cookie_file(cookie_file, domain))
        return session

    if browser:
        jar = load_browser_cookie_jar(browser, domain)
        session.cookies.update(jar)

    return session


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    parser.add_argument(
        "--cookie-file",
        default="",
        help="Archivo cookies.txt (formato Netscape) exportado desde extensión del navegador.",
    )
    parser.add_argument("--output-dir", default="exports", help="Carpeta donde se guardan los .html")
    parser.add_argument("--max-pages", default=300, type=int, help="Límite de páginas por lista para evitar loops")
    parser.add_argument(
        "--with-progress",
        action="store_true",
        default=False,
        help="Visita cada manga para obtener capítulos leídos/totales (más lento, agrega delay entre peticiones).",
    )
    return parser.parse_args(argv)


def interactive_auth_menu(args: argparse.Namespace) -> argparse.Namespace:
    if args.browser or args.cookie or args.cookie_file:
        return args

    options = [
        ("chrome", "Usar cookies de Chrome"),
        ("firefox", "Usar cookies de Firefox"),
        ("edge", "Usar cookies de Edge"),
        ("brave", "Usar cookies de Brave"),
        ("opera", "Usar cookies de Opera"),
        ("cookie", "Pegar cookie manual"),
        ("cookie-file", "Ruta a cookie file (cookies.txt)"),
        ("none", "Continuar sin autenticación"),
    ]

    print("\nNo indicaste --browser ni --cookie.")
    print("Selecciona cómo quieres autenticarte:")
    for idx, (_, label) in enumerate(options, start=1):
        print(f"  {idx}. {label}")

    while True:
        selection = input("Opción [1-8]: ").strip()
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
        elif key == "cookie-file":
            args.cookie_file = input("Ruta del archivo cookies.txt: ").strip()
        elif key != "none":
            args.browser = key
        return args


def main(argv: list[str] | None = None) -> int:
    args = interactive_auth_menu(parse_args(argv))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_base = urlparse(args.base_url)
    cookie_domain = args.cookie_domain or parsed_base.hostname or ""
    try:
        session = build_session(args.cookie, args.browser, args.cookie_file, cookie_domain)
    except RuntimeError as exc:
        print(f"[x] {exc}")
        return 1

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

        if args.with_progress and items:
            print(f"  [*] Obteniendo progreso de capítulos ({len(items)} mangas)...")
            items = enrich_items_with_progress(session, items)

        filename = sanitize_filename(manga_list.title) + ".html"
        destination = output_dir / filename
        destination.write_text(render_html(manga_list.title, items, with_progress=args.with_progress), encoding="utf-8")
        print(f"[✓] Exportado: {destination} ({len(items)} elementos)")

    print(f"\n[✓] Terminado. Archivos en: {output_dir.resolve()} | Elementos totales: {total_items}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
