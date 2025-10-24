# Intranet

## Descripción
Intranet es una aplicación que permite visualizar información bajada desde la API de Buk en un dashboard y en distintos reportes. Facilita la gestión y monitoreo de datos de la organización de manera centralizada, incluyendo reportes de horas trabajadas, inasistencias y movimientos de personal.

---

## Tecnologías usadas
- Python (Flask)  
- Docker / Docker Compose  
- MySQL  
- HTML / CSS / JavaScript  
- Git / GitHub  

---

## Estructura de carpetas
intranet/
├── app/
│ ├── blueprints/
│ │ ├── admin/
│ │ ├── auth/
│ │ ├── dashboard/
│ │ ├── desvinculaciones/
│ │ └── scopes/
│ ├── models/
│ ├── static/
│ ├── templates/
│ ├── extensions.py
│ └── init.py
├── config.py
├── config_loader.py
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── requirements.txt
└── README.md

yaml
Copiar código

> Nota: Algunos directorios incluyen subcarpetas para rutas, templates y archivos estáticos de cada módulo.

---

## Instalación y ejecución local
1. Clona el repositorio:
```bash
git clone https://github.com/blopez000/intranet.git
cd intranet
Construye y levanta los contenedores Docker:

bash
Copiar código
docker-compose up --build
Accede a la aplicación desde tu navegador:

arduino
Copiar código
http://localhost:8000
Asegúrate de tener Docker y WSL (Windows Subsystem for Linux) instalados y funcionando correctamente.

Comandos útiles para desarrollo
bash
Copiar código
# Ver estado del repo
git status

# Agregar cambios y crear commit
git add .
git commit -m "Mensaje descriptivo"

# Subir cambios al remoto
git push origin main

# Traer cambios del remoto
git pull origin main

# Crear y cambiar a una rama nueva
git checkout -b feature/nueva_funcionalidad
git push -u origin feature/nueva_funcionalidad

# Eliminar ramas locales y remotas
git branch -d nombre_rama
git push origin --delete nombre_rama
Uso
Ingresa al dashboard para visualizar la información de la API de Buk.

Genera reportes de:

Horas trabajadas

Inasistencias

Movimientos de personal

Nomina y rotaciones

Autor
Benjamín Patricio López Fernández
Correo: blopez@id-logistics.com
