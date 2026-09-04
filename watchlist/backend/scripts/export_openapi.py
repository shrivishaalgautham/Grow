import json
from pathlib import Path

from app.main import create_app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    OUTPUT.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
