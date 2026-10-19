import json
from pathlib import Path
from .models import Protein

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_proteins.json"

def load_demo(path: Path = DEFAULT_PATH) -> list[Protein]:
    return [Protein(**p) for p in json.loads(Path(path).read_text())]
