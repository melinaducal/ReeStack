# INFORME_TECNICO.md

## Stack Tecnológico
- **Frontend:** React 18 + Vite 5, React Router DOM, Axios
- **Backend:** FastAPI 0.115.4, SQLAlchemy 2.0.36, Uvicorn
- **Base de datos:** SQLite
- **Autenticación:** JWT (python-jose), passlib + bcrypt
- **Validación:** Pydantic v2

## Arquitectura
Arquitectura cliente-servidor con API REST. Frontend SPA, backend FastAPI con routers modulares.

## Modelos
- **User:** usuarios con auth, tema personalizado
- **Item:** libros/películas/series/música/papers con progreso de lectura, portada
- **Comment:** comentarios con calificación y spoiler flag

## Endpoints principales
- `/auth/*` - autenticación y tema
- `/items/*` - CRUD de items y progreso
- `/comments/*` - comentarios y calificaciones

## Características
- Feed editorial estilo Substack/Goodreads
- Seguimiento de lectura con progreso
- Sistema de spoilers en comentarios
- Temas personalizables por usuario
- Animación de entrada a librería
- Búsqueda con Open Library

## Seguridad
- Contraseñas hasheadas con bcrypt
- JWT tokens
- Validación de email, contraseña fuerte, edad >=14
- CORS configurado
- Protección de rutas en frontend
