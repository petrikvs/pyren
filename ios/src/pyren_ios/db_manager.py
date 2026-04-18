"""Import/inspect CLIP and DDT database zips in the iOS Documents folder.

pyren's `mod_db_manager.find_DBs()` globs for `pyrendata*.zip` (CLIP) and
`DDT2000data*.zip` (DDT) in the current working directory. On iOS we
chdir into `~/Documents`, so importing a database just means copying the
user-picked zip there with the expected name pattern.

Classification peeks at the zip's top-level entries:

  - CLIP zips contain: `EcuRenault`, `Vehicles`, `Location`, `Params`, ...
  - DDT zips contain:  `ecus`, `graphics`, `images`, `vehicles`.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


CLIP_MARKERS = {"EcuRenault", "EcuDacia", "EcuRsm", "Vehicles",
                "Location", "Params", "NML", "DocDB_RU"}
DDT_MARKERS = {"ecus", "graphics", "images", "vehicles"}


@dataclass
class DBStatus:
    clip: Optional[Path] = None
    ddt: Optional[Path] = None


class DatabaseManager:
    def __init__(self, work_dir: Path) -> None:
        self._work_dir = work_dir
        self._work_dir.mkdir(parents=True, exist_ok=True)

    @property
    def work_dir(self) -> Path:
        return self._work_dir

    def scan(self) -> DBStatus:
        clip_zips = sorted(self._work_dir.glob("pyrendata*.zip"), reverse=True)
        ddt_zips = sorted(self._work_dir.glob("DDT2000data*.zip"), reverse=True)
        return DBStatus(
            clip=clip_zips[0] if clip_zips else None,
            ddt=ddt_zips[0] if ddt_zips else None,
        )

    @staticmethod
    def classify(zip_path: Path) -> Optional[str]:
        """Return 'clip', 'ddt', or None based on top-level zip entries."""
        try:
            with zipfile.ZipFile(zip_path) as z:
                names = z.namelist()
        except (zipfile.BadZipFile, OSError):
            return None
        top = {n.split("/", 1)[0] for n in names if n}
        # CLIP has "Vehicles" (uppercase V) or "EcuRenault"; DDT also has
        # "vehicles" (lowercase) so check uppercase markers first.
        if top & (CLIP_MARKERS - {"Vehicles"}) or "Vehicles" in top:
            return "clip"
        if "ecus" in top and top & DDT_MARKERS:
            return "ddt"
        return None

    def import_zip(self, src: Path, kind: str) -> Path:
        """Copy src into work_dir, renamed to match pyren's glob pattern.

        Removes any pre-existing zip of the same kind so pyren picks up
        the new one on next launch.
        """
        if kind == "clip":
            prefix = "pyrendata"
        elif kind == "ddt":
            prefix = "DDT2000data"
        else:
            raise ValueError(f"unknown db kind: {kind!r}")

        if src.name.startswith(prefix) and src.name.endswith(".zip"):
            dest_name = src.name
        else:
            # Keep original stem as suffix so the user can tell versions apart.
            dest_name = f"{prefix}_{src.stem}.zip"

        for old in self._work_dir.glob(f"{prefix}*.zip"):
            try:
                old.unlink()
            except OSError:
                pass

        dest = self._work_dir / dest_name
        shutil.copyfile(src, dest)
        return dest
