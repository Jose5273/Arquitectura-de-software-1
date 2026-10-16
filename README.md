# Arquitectura-de-software-1

instagram_recolectar ejecuta brave.exe con --user-data-dir apuntando a la carpeta de perfiles y --profile-directory=Default. Además inyecta un script CDP que oculta navigator.webdriver y simula idiomas/plugins para reducir la huella de automatización.

recolectar_perfil() saca el nombre visible, biografía, imagen, y los contadores de seguidores/seguidos/publicaciones desde los <meta property="og:..."> del HTML.

recolectar_enlaces_publicaciones() hace scroll en el perfil y recoge hasta 25 URLs de posts/reels.

recolectar_publicaciones() entra a cada URL, espera a que cargue el <article>, y extraer_datos_publicacion() busca la imagen real del post (excluyendo la foto de perfil por contenedor y por tamaño).

DescargadorImagenes baja cada imagen a salida_instagram/imagenes/ con requests, y guarda la ruta local en el registro.

ModalSeguidores abre el modal haciendo clic en el enlace del contador, localiza el contenedor scrollable, hace scroll hasta 50 nombres, y extrae los href de perfil válidos. Cierra el modal con ESC.

Exportador escribe perfil.csv, publicaciones.csv, seguidores.csv, seguidos.csv y datos_instagram.json en salida_instagram/.

La razón del porque usar Brave como navegador son:
1. Es un navegador basado en chromium y que se conecta con Selenium
2. Se probó con navegadores Chrome, Tor y Edge, Tor fue descartado por la complejidad de su estructura, Edge por no poder conectar satisfactoriamente con Selenium y Chrome porque Instagram detectaba la cuenta como un bot.
3. Brave guarda la sesión de Instagram y sus credenciales en el perfil principal.

Algunos Errores y sus respectivas correcciones fueron:
1. Selenium abria directamente un perfil nuevo en el navegador, detectad como un bot por Instagram y mostrando el mensaje genérico "La información de inicio de sesión que ingresaste es incorrecta" corregido con las credenciales guardadas, lo que vendría a ser las cookies de inicio de sesión que funcionan como llave de ingreso para el scrapeo.
2. La versión de Chromium utilizada por Selenium fallaba al conectarse con Brave al estar desactualizada, se optó por descargar chromedriver-win64.zip de la versión 155.0.8059.39 se paso a 155.0.8059.80 para estar actualizada a la versión 1.97.57 de Brave.
3. Para conectar el perfil de Brave junto con Selenium y no abriera uno nuevo, se añadió dentro del código una ruta hacia el perfil de Usuario de Windows y otra hacia el perfil Default de Brave.

Consideraciones:
1. El código fue realizado en Visual Studio Code versión 1.142.0
2. Chromium 155.0.8059.80
3. Brave 1.97.57 con Chromium 155.0.8059.80

Bibliografía:
1. ChatGPT (Formulación y estructuración del programa)
2. DeepSeek (Generación de código)
