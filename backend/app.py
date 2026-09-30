# Importamos la clase Flask desde la librería que instalamos
from flask import Flask

# Inicializamos la aplicación de Flask, coso esto crea nuestro servidor web xd
app = Flask(__name__)

# Definimos una ruta ("decorador") El símbolo ese de la barra significa q es la página principal (la raíz del sitio).
@app.route('/')
def home():
    # Esta función se ejecuta cada que alguien entra a la URL principal de nuestro backend.
    # Por ahora devuelve un texto simple para confirmar que la conexión funciona.
    return "El backend pro de AeroPlate está conectado y funcionando lol"

# Este bloque verifica que el script se esté ejecutando directamente.
if __name__ == '__main__':
    # Arrancamos el servidor de desarrollo
    # host='0.0.0.0' permite q el servidor acepte conexiones externas (indispensable para la nube de Render)
    # port=5000 es el puerto numérico por donde va a escuchar las peticiones.
    app.run(host='0.0.0.0', port=5000)
