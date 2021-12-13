from pathlib import Path

DATA_DIR = Path(__file__).parent.absolute()  # / "data"
REF_DIR = DATA_DIR / Path("expected_data")
INPUT_DIR = DATA_DIR / Path("input_data")
