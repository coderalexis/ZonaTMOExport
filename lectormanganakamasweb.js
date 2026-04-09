(async function () {
    let allItems = [];
    let page = 1;

    // Detectar la URL base según el elemento activo
    const activeElements = document.querySelector(".element-header-bar .element-header-bar-element.active a");
    const baseUrl = activeElements ? activeElements.href : "https://zonatmo.com/profile/read";
    const seleccionTitulo = activeElements
        ?.querySelector("small.element-header-bar-element-title")
        ?.textContent.trim() || "Mi Lista de Manga";

    console.log(`URL: ${baseUrl}`);
    console.log(`TITULO: ${seleccionTitulo}`);

    // Obtener todos los elementos paginados
    while (true) {
        console.log(`Páginas: ${page}...`);

        // Realizar la petición con la URL base
        const response = await fetch(`${baseUrl}?page=${page}`);
        if (!response.ok) {
            console.error("Error al cargar las páginas");
            break;
        }

        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // Seleccionar los ítems (nombre/link)
        const items = [...doc.querySelectorAll(".element.proyect-item")];
        if (items.length === 0) {
            console.log("No hay más ítems que cargar.");
            break;
        }

        // Extraer los títulos, enlaces e imágenes
        items.forEach(item => {
            const title = item.querySelector(".thumbnail-title h4.text-truncate")?.getAttribute("title")?.trim() || "Sin título";
            const link = item.querySelector("a")?.getAttribute("href")?.trim() || "#";
            
            const identifier = item.getAttribute("data-identifier");
            
            // Buscar el estilo CSS que contiene la imagen
            const styleTag = item.querySelector("style");
            let imageUrl = "Sin imagen";
            
            if (styleTag) {
                const match = styleTag.textContent.match(/background-image:\s*url\(['"]?(.*?)['"]?\);/);
                if (match) {
                    imageUrl = match[1]; // Extrae la URL correcta de la imagen
                }
            }

            allItems.push({ title, link, imageUrl });
        });

        console.log(`Página ${page} procesada.`);
        page++;
    }

    // Generar el contenido del HTML
    console.log(`Generando archivo HTML para la lista: ${seleccionTitulo}`);

    const htmlContent = `
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>${seleccionTitulo}</title>
            <style>
                body {
                    background-color: #121212;
                    color: #ffffff;
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin: 0;
                    padding: 0;
                }
                .topnav {
                    background-color: #1e1e1e;
                    padding: 15px;
                    font-size: 20px;
                    font-weight: bold;
                }
                .container {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 90vh;
                    flex-direction: column;
                }
                table {
                    width: 80%;
                    border-collapse: collapse;
                    background-color: #222;
                    border-radius: 10px;
                    overflow: hidden;
                }
                th, td {
                    padding: 15px;
                    border: 1px solid #444;
                    text-align: center;
                }
                th {
                    background-color: #333;
                    color: #fff;
                }
                a {
                    color: #1e90ff;
                    text-decoration: none;
                    font-weight: bold;
                }
                a:hover {
                    text-decoration: underline;
                }
                img {
                    width: 60px;
                    height: 80px;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>

            <div class="topnav">${seleccionTitulo}</div>
            
            <div class="container">
                <table>
                    <thead>
                        <tr>
                            <th>Imagen</th>
                            <th>Título</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${allItems.map(item => `
                            <tr>
                                <td><img src="${item.imageUrl}" alt="${item.title}"></td>
                                <td><a href="${item.link}" target="_blank">${item.title}</a></td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>

        </body>
        </html>
    `;

    // Crear y descargar el archivo HTML
    const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Lista de ${seleccionTitulo}.html`;
    a.click();
    URL.revokeObjectURL(url);

    console.log("Archivo HTML exportado con éxito.");
})();