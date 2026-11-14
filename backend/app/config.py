from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-only-secret-change-me-dev-only-secret-change-me"
DEFAULT_DEMO_PASSWORD = "demo-password-for-local-use"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://studease:studease@127.0.0.1:15433/studease"
    test_database_url: str | None = None
    seed: int = 20261022
    cors_origins: str = "http://localhost:5173"
    app_url: str = "http://localhost:5173"           # base for links inside emails

    jwt_secret: str = DEFAULT_SECRET
    jwt_ttl_minutes: int = 8 * 60
    demo_password: str = DEFAULT_DEMO_PASSWORD      # password of the seeded demo logins (S-6 forces a real one in prod)

    smtp_host: str | None = None                     # outbound mail; unset means mail is skipped
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_from: str | None = None

    @property
    def test_url(self) -> str:
        """Database used by the tests: TEST_DATABASE_URL, else the main URL with `_test` on the database name."""
        return self.test_database_url or self.database_url.rsplit("/", 1)[0] + "/studease_test"

    def check(self) -> None:
        """S-6: refuse to start in production with a default or weak secret."""
        if self.env == "prod":
            if self.jwt_secret == DEFAULT_SECRET or len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET must be set to 32+ random characters in prod")
            if self.demo_password == DEFAULT_DEMO_PASSWORD or len(self.demo_password) < 12:
                raise RuntimeError("DEMO_PASSWORD must be set to 12+ characters in prod")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
