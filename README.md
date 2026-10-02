​ AeroPlate — Backend & Sistema de Pagos
​AeroPlate es una plataforma web desarrollada en el marco de proyectos de software y prácticas profesionalizantes, diseñada para ofrecer una experiencia de comercio electrónico funcional e integrada con pasarelas de pago y bases de datos en la nube.
​- Tecnologías y Stack Utilizado
​Backend: Python con FastAPI (asíncrono, rápido y con validación automática mediante Pydantic).
​Cliente HTTP: httpx para las peticiones a pasarelas externas.
​Base de Datos y Autenticación: Supabase (PostgreSQL + Auth mediante RPCs y triggers).
​Pasarela de Pagos: API de Mercado Pago (Checkout de Preferencias, Webhooks y verificación de pagos).
​Despliegue (Deployment): Render (Entorno cloud con despliegue continuo desde GitHub).
​Gestión de Correo: Brevo (para notificaciones automáticas de compras y vencimientos).
​-Arquitectura y Flujos Principales (DFD)
​El sistema implementa un flujo robusto de lógica de negocios dividido en los siguientes módulos:
​Gestión de Clientes y Autenticação:
​Endpoints protegidos mediante dependencias (solo_cliente) que validan tokens de Supabase.
​Ciclo de Vida de Pedidos y Stock:
​Validación de carritos, creación de pedidos en estado pendiente, y rutinas de barrido en segundo plano (BackgroundTasks) para expirar pedidos vencidos.
​Pasarela de Pagos (Mercado Pago):
​Inicio de Pago (POST /pagos/{id}/iniciar): Genera de forma dinámica la preferencia de pago en Mercado Pago, asociando ítems, external_reference (ID del pedido) y URLs de retorno (back_urls) hacia el frontend.
​Verificación Manual (POST /pagos/{id}/verificar): Permite consultar de forma segura el estado del pago directamente a la API de Mercado Pago al retornar del checkout, asegurando que nadie pueda falsificar una aprobación.
​Webhooks (POST /pagos/webhook): Recibe notificaciones asíncronas desde los servidores de Mercado Pago, revalidando el token de acceso antes de confirmar definitivamente la transacción en la base de datos mediante procedimientos almacenados (confirmar_pago).
​Modo Simulado (POST /pagos/{id}/simular): Funcionalidad de respaldo ante la ausencia del token de producción, permitiendo validar flujos completos sin pasarela real.
