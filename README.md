# ReeStack

Red social cultural para registrar libros, películas, series, música y papers, compartir pensamientos y reseñas.

## Tecnologías
- **Frontend:** React + Vite
- **Backend:** Python + FastAPI
- **Base de datos:** SQLite
- **Autenticación:** JWT

## Estructura
```
ReeStack/
├── .opencode/          # configuración y agentes
├── backend/            # API FastAPI y SQLite
├── frontend/           # aplicación React + Vite
├── assistant/          # chatbot y sistema de recomendaciones
├── mcp-interno/        # herramientas MCP propias
├── docs/               # documentación
├── specs/              # especificaciones
├── AGENTS.md
├── ESTADO.md
├── INFORME_TECNICO.md
└── README.md
```

## Instalación

### Backend
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Funcionalidades
- Feed editorial con publicaciones
- Mi Stack - colección personal
- Seguimiento de lectura con progreso
- Comentarios con calificaciones y spoilers
- Búsqueda con Open Library
- Temas personalizables
- Autenticación completa
