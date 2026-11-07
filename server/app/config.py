from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    node_id: str = "api-coordinator"
    db_primary: str = "postgres-primary"
    db_replicas: str = "postgres-replica-1,postgres-replica-2,postgres-replica-3"
    db_port: int = 5432
    db_user: str = "tickets"
    db_password: str = "tickets_dev"
    db_name: str = "tickets"

    # Helpers dos nós distribuídos
    helper_nodes: str = "helper-node-1,helper-node-2,helper-node-3"
    helper_port: int = 9000

    @property
    def replica_hosts(self) -> list[str]:
        return [h.strip() for h in self.db_replicas.split(",") if h.strip()]

    @property
    def all_hosts(self) -> list[str]:
        return [self.db_primary, *self.replica_hosts]

    @property
    def helper_hosts(self) -> list[str]:
        return [h.strip() for h in self.helper_nodes.split(",") if h.strip()]


settings = Settings()
