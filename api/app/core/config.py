
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    # Quando definida, o rate limiter usa Redis (compartilhado entre workers).
    RATE_LIMIT_REDIS_URL: str = ""
    
    MERCADO_PAGO_ACCESS_TOKEN: str = ""
    MERCADO_PAGO_PUBLIC_KEY: str = ""
    
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
    
    ALLOWED_HOSTS: list[str] = ["*"]
    
    # Storage S3-compatível (Cloudflare R2 / Backblaze B2 / MinIO / AWS S3)
    STORAGE_ENDPOINT: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    STORAGE_BUCKET: str = "wr-videos"
    STORAGE_REGION: str = "auto"
    STORAGE_WATCH_URL_EXPIRATION: int = 7200  # segundos

    # Chave de criptografia para secrets de tenant (32 bytes base64).
    # Em produção deve ser definida via env. Se vazia, fallback para uma
    # chave derivada da SECRET_KEY (apenas desenvolvimento).
    TENANT_SECRET_ENCRYPTION_KEY: str = ""

settings = Settings()
