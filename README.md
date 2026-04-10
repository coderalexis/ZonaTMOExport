# ZonaTMOExport (modo automático)

Este repositorio ahora incluye un script de **una sola ejecución** para exportar listas de ZonaTMO/LectorManga a HTML sin pegar código manualmente en la consola del navegador.

## Requisitos

- Python 3.9+
- Instalar dependencias:

```bash
pip install requests beautifulsoup4 browser-cookie3
```

## Uso rápido

## Interfaz visual para Windows (recomendada para usuarios no técnicos)

Ejecuta:

```bash
python gui_windows.py
```

La ventana solo te pide:
- `cookies.txt` (exportado desde la extensión **Get cookies.txt LOCALLY**)
- Carpeta de salida

Y luego pulsas **Exportar listas**.

### Opción fácil (recomendada): leer cookies del navegador automáticamente

1. Inicia sesión en ZonaTMO/LectorManga desde tu navegador (Chrome/Firefox/Edge/Brave/Opera).
2. Ejecuta:

```bash
python export_lists.py \
  --base-url "https://lectormanga.nakamasweb.com/profile/follow" \
  --browser chrome \
  --output-dir "exports"
```

> Cambia `--browser` por `firefox`, `edge`, `brave`, etc. según uses.
> Si sale `PermissionError` al leer cookies de Chrome, cierra completamente el navegador (incluyendo procesos en segundo plano) o usa `--cookie-file`.
> Si sale error de descifrado (`DPAPI`, `MAC check failed`, `Unable to get key for cookie decryption`), usa `--cookie-file`: es el método más estable en Windows.

### Opción manual: pasar cookie copiada de DevTools

1. Abre tu navegador logueado y entra a ZonaTMO/LectorManga.
2. Presiona `F12` → pestaña **Network**.
3. Recarga la página y abre una petición de tipo *document* (normalmente la primera).
4. En **Headers** busca `cookie` (Request Headers).
5. Copia todo el valor (ejemplo: `a=b; c=d; ...`) y ejecútalo así:

```bash
python export_lists.py \
  --base-url "https://lectormanga.nakamasweb.com/profile/follow" \
  --cookie "a=b; c=d" \
  --output-dir "exports"
```

### Opción súper simple: menú interactivo

Si ejecutas solo:

```bash
python export_lists.py
```

el script detecta que no pasaste `--browser` ni `--cookie` y te muestra un menú para escoger navegador, pegar cookie manual o indicar archivo `cookies.txt`.

### Opción robusta: `cookies.txt` exportado desde extensión

1. Instala una extensión tipo **Cookie-Editor** o similar.
2. Exporta cookies del sitio en formato **Netscape cookies.txt**.
3. Ejecuta:

```bash
python export_lists.py \
  --base-url "https://lectormanga.nakamasweb.com/profile/follow" \
  --cookie-file "C:\\ruta\\cookies.txt" \
  --output-dir "exports"
```

## URLs de listas soportadas por defecto (lectormanga.nakamasweb.com)

- `https://lectormanga.nakamasweb.com/profile/watch`
- `https://lectormanga.nakamasweb.com/profile/pending`
- `https://lectormanga.nakamasweb.com/profile/follow`
- `https://lectormanga.nakamasweb.com/profile/wish`
- `https://lectormanga.nakamasweb.com/profile/have`
- `https://lectormanga.nakamasweb.com/profile/abandoned`

## Resultado

- Genera un archivo `.html` por cada lista detectada.
- Cada HTML contiene tabla con imagen + título + enlace.
- Por defecto, los archivos se guardan en `./exports`.

## Opciones útiles

```bash
python export_lists.py --help
```

Parámetros principales:

- `--base-url`: perfil/lista base (ahora default: `https://lectormanga.nakamasweb.com/profile/follow`).
- `--cookie`: cookie del navegador.
- `--browser`: lee cookies automáticamente desde tu navegador local.
- `--cookie-domain`: dominio para filtrar cookies (si no se pasa, usa el dominio de `--base-url`).
- `--cookie-file`: archivo `cookies.txt` (formato Netscape) como alternativa a `--browser`.
- `--output-dir`: carpeta destino.
- `--max-pages`: límite de páginas por lista (default: `300`).

## Pasar a ejecutable de Windows (.exe)

1. Instala Python 3.9+.
2. Instala dependencias:

```bash
pip install requests beautifulsoup4 browser-cookie3 pyinstaller
```

3. (Importante) Instala la extensión **Get cookies.txt LOCALLY** en tu navegador para exportar `cookies.txt`.
4. Genera el ejecutable:

```bash
pyinstaller --onefile --windowed gui_windows.py
```

5. El `.exe` quedará en:

```text
dist/gui_windows.exe
```

6. Para usarlo:
   - Exporta `cookies.txt` desde la extensión.
   - Abre `gui_windows.exe`.
   - Selecciona `cookies.txt` y carpeta de salida.
   - Pulsa **Exportar listas**.
