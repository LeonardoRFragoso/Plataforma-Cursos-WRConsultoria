from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, courses, classes, students, enrollments, payments, certificates, companies, lessons

app = FastAPI(
    title="WR Plataforma de Cursos",
    description="API para gestão de cursos e treinamentos NR",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["courses"])
app.include_router(classes.router, prefix="/api/v1/classes", tags=["classes"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(enrollments.router, prefix="/api/v1/enrollments", tags=["enrollments"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(certificates.router, prefix="/api/v1/certificates", tags=["certificates"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["companies"])
app.include_router(lessons.router, prefix="/api/v1/lessons", tags=["lessons"])

@app.get("/")
async def root():
    return {"message": "WR Plataforma de Cursos API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}
