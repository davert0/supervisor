import sys
import shutil
from pathlib import Path
from datetime import datetime
from config import DATABASE_PATH


def main() -> None:
    project_root = Path(__file__).resolve().parent
    db_path = project_root / DATABASE_PATH
    if not db_path.exists():
        sys.stderr.write(f"database file not found: {db_path}\n")
        sys.exit(1)
    backup_dir = project_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    print(str(backup_path))


if __name__ == "__main__":
    main()

