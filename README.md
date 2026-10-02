
##  AeroPlate — Sistema E-Commerce & Pasarela de Pagos

Plataforma web de comercio electrónico desarrollada en el marco de proyectos tecnológicos y prácticas profesionalizantes, diseñada para ofrecer una experiencia completa de gestión de pedidos, administración de stock y cobros en línea integrados con **Mercado Pago**. La aplicación se encuentra completamente funcional y desplegada en entornos de producción en línea.

---

##  Enlaces de Acceso y Producción

* **Repositorio oficial (GitHub):** [Rimbis/Olimpiadas-Programacion](https://github.com/Rimbis/Olimpiadas-Programacion/tree/main)
* **Sistema Backend en Línea (Render):** [aeroplate-backend.onrender.com](https://aeroplate-backend.onrender.com)
* **Frontend - Interfaz de Clientes (Vercel):** [olimpiadas-programacion-frontend.vercel.app](https://olimpiadas-programacion-frontend.vercel.app/)
* **Panel de Administración (Vercel):** [Panel Admin AeroPlate](https://olimpiadas-programacion-frontend.vercel.app/admin.html)

---

##  Tecnologías y Stack Utilizado

* **Backend / API:** Python con **FastAPI** (asíncrono y de alto rendimiento).
* **Validación de Datos:** **Pydantic**.
* **Cliente HTTP:** **httpx** para solicitudes asíncronas.
* **Base de Datos y Autenticación:** **Supabase** (PostgreSQL en la nube, funciones RPC y triggers).
* **Pasarela de Pagos:** API de **Mercado Pago** (Checkout de preferencias y webhooks).
* **Despliegue y Cloud (CI/CD):** 
  - Backend alojado en **Render**.
  - Frontend y Panel Admin alojados en **Vercel**.
* **Servicios de Correo:** **Brevo** para notificaciones transaccionales.

---

##  Estructura General del Repositorio

El proyecto se organiza de manera modular para separar la lógica del servidor, la interfaz visual y la documentación técnica:

- **backend/**: Servidor de la API construido en Python con FastAPI.
  - **app/routers/**: Endpoints y rutas HTTP encargados de gestionar clientes, catálogos y transacciones de pago.
  - **app/services/**: Módulos de lógica secundaria (envío de correos automáticos mediante Brevo y control de vencimientos).
  - **app/config.py**: Validador y gestor seguro de variables de entorno mediante Pydantic.
  - **app/db.py**: Inicializador de la conexión y cliente de Supabase.
  - **app/auth.py**: Sistema de dependencias de seguridad encargado de validar tokens JWT de usuarios.
  - **app/main.py**: Archivo principal que inicializa la aplicación FastAPI, middlewares y CORS.
  - **requirements.txt**: Listado de dependencias de Python necesarias.
  - **.env.example**: Plantilla de configuración de entorno.
- **frontend/**: Archivos estáticos y páginas web de la interfaz de usuario y panel de control.
- **documentos/**: Diagramas formales (DFD, DER) y documentación institucional del proyecto.
- **imagen-logo/**: Recursos gráficos y logotipos institucionales de la marca.
- **README.md**: Documentación técnica detallada del proyecto.

---

## 📄 ¿Qué hace cada archivo y componente del Backend?

* **`app/main.py`**: Configura y levanta la API asíncrona, conectando los enrutadores y habilitando el intercambio seguro de recursos (CORS).
* **`app/config.py`**: Lee de forma estricta las credenciales del entorno mediante Pydantic Settings.
* **`app/db.py`**: Conecta la aplicación con la base de datos cloud en Supabase.
* **`app/auth.py`**: Intercepta las peticiones HTTP y filtra el acceso mediante la función `solo_cliente`, garantizando que solo usuarios autorizados operen.
* **`app/routers/pagos.py`**: Módulo central transaccional. Se encarga de:
  - Generar las preferencias de pago dinámicas en la API de Mercado Pago.
  - Configurar las URLs de redireccionamiento al frontend (`back_urls`).
  - Validar de forma segura los pagos mediante consultas directas a la pasarela (`/verificar`).
  - Procesar notificaciones asíncronas desatendidas (`/webhook`).
  - Proveer un sistema de respaldo o modo simulado (`/simular`) para entornos locales o pruebas sin token real.
* **`app/services/mails.py`**: Automatiza las alertas por correo electrónico ante cambios en los estados de compra utilizando Brevo.
* **`app/services/vencimientos.py`**: Ejecuta tareas de barrido en segundo plano para expirar pedidos pendientes de pago.

---

##  Guía para Clonar desde GitHub y Usar en VS Code

Si querés descargar el proyecto en tu computadora, abrirlo en **Visual Studio Code** y ponerlo a funcionar localmente, seguí estos pasos detallados:

### 1. Clonar el repositorio desde la terminal o VS Code
Abrí tu terminal y cloná el proyecto ejecutando:
```bash
git clone [https://github.com/Rimbis/Olimpiadas-Programacion.git](https://github.com/Rimbis/Olimpiadas-Programacion.git)
```
Luego, abrí Visual Studio Code, ve a File > Open Folder... y seleccioná la carpeta recién descargada Olimpiadas-Programacion.
### 2 Hay que abrir y configurar el entorno del Backend en VS Code
   1-Dentro de VS Code, abrí una terminal integrada (Terminal > New Terminal).
   2-Entrá a la carpeta del backend con:
```bash
cd backend
```
   3- Creá un entorno virtual de Python para aislar las dependencias:
```bash
python -m venv venv
```

   4-Activá el entorno virtual:
     ​En Windows (CMD / PowerShell): venv\Scripts\activate
     ​En Linux / macOS: source venv/bin/activate
   5- Instalación de dependencias:
```bash
pip install -r requirements.txt
```

###3. 3. Configurar las variables de entorno
​Dentro de la carpeta backend/, creá un archivo llamado .env.
​Podés guiarte copiando el archivo .env.example y completando los siguientes campos obligatorios para que la app conecte con Supabase y Mercado Pago:
​SUPABASE_URL
​SUPABASE_SERVICE_KEY
​SUPABASE_ANON_KEY
​MP_ACCESS_TOKEN (Opcional: dejar en blanco si se desea operar en modo simulado)
​BASE_URL

###4. ​4. Ejecutar el servidor localmente
​Una vez configurado todo, ejecutá el servidor de desarrollo con Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```
La API quedará corriendo localmente en http://localhost:8000 y podrás acceder a la documentación interactiva en http://localhost:8000/docs.

### Arquitectura y Flujo de Pagos en Línea (DFD)
​Creación del Pedido: El usuario genera una compra desde el frontend desplegado en Vercel; el sistema registra el pedido en Supabase con estado pendiente.
​Inicio del Cobro (POST /pagos/{id}/iniciar): El backend en Render solicita a Mercado Pago una preferencia de pago enviando los ítems, el monto total y el ID del pedido como external_reference.
​Checkout y Retorno: El cliente abona en la plataforma oficial de Mercado Pago y es redirigido automáticamente de vuelta a la aplicación web.
​Verificación y Confirmación: El cliente ejecuta la verificación manual o el servidor procesa el pago de forma segura a través de los webhooks, impactando el stock y confirmando la transacción en tiempo real mediante procedimientos almacenados en la base de datos.




      

