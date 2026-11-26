"""Backend that writes the simulator-neutral CityG manifest."""

from pathlib import Path

from cityg.schemas import City
from cityg.serialization import save_json


class ManifestBackend:
    def compile(self, city: City, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        return [save_json(city, output_dir / "city.json")]

