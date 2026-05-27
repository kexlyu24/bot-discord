from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.database import engine
from app.models.base import Base
from app.api.v1 import auth, guilds, player, admin, ws

# Initialize Database tables
def init_db():
    # Creates SQLite tables if they do not exist
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Discord Music Bot Dashboard API",
    description="FastAPI Backend for bot-discord real-time dashboard controls.",
    version="1.0.0"
)

# Register custom exception handlers for uniform API error responses
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Extract error message from fields validation
    errors = exc.errors()
    msg = errors[0].get("msg") if errors else "Validation error"
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": f"{msg}: {errors}"}
    )

# CORS middleware setup to allow dashboard web client to connect
origins = ["http://localhost:3000"]
if settings.FRONTEND_URL:
    frontend_origin = settings.FRONTEND_URL.rstrip("/")
    if frontend_origin not in origins:
        origins.append(frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

# Include all API Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(guilds.router, prefix="/api/v1/guilds", tags=["Guilds"])
app.include_router(player.router, prefix="/api/v1/player", tags=["Player Controls"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin Settings"])
app.include_router(ws.router, prefix="/api/v1/ws", tags=["Realtime Websockets"])

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
