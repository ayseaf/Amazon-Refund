import uvicorn

from apt.config import AppConfig
from apt.main import create_app


def main() -> None:
    config = AppConfig.from_env()
    uvicorn.run(create_app(config), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
