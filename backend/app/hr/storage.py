"""Stockage des CV sur disque local, derrière une interface étroite.

`FileStore` est volontairement minimal — `save`, `open`, `delete` — pour que
le passage à un stockage objet (S3) ne touche que ce fichier. Les chemins sont
construits par la plateforme, JAMAIS à partir du nom fourni par le client :
`{org_id}/{job_id}/{uuid}.{ext}`. Un nom d'origine peut contenir des
séparateurs, des `..`, ou l'identité du candidat ; il est conservé en base
pour l'affichage, jamais sur le disque.

Le type réel est vérifié sur les octets (signature), pas sur l'extension ni
sur le `Content-Type` déclaré : un exécutable renommé `.pdf` est rejeté.
"""

import io
import uuid
import zipfile
from pathlib import Path
from typing import BinaryIO

from app.config import settings

# backend/app/hr/storage.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Types acceptés : (extension, type MIME).
ALLOWED_KINDS: dict[str, tuple[str, str]] = {
    "pdf": (".pdf", PDF_MIME),
    "docx": (".docx", DOCX_MIME),
}

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"
# Un .docx est un conteneur OPC : un ZIP qui contient le corps du document.
_DOCX_MEMBER = "word/document.xml"


def sniff_kind(data: bytes) -> str | None:
    """Type réel d'un téléversement : "pdf", "docx", ou None si non autorisé."""
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_ZIP_MAGIC):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
        except (zipfile.BadZipFile, OSError):
            return None
        # Un .xlsx ou un .odt sont aussi des ZIP : on exige le corps Word.
        return "docx" if _DOCX_MEMBER in names else None
    return None


class FileStore:
    """Fichiers d'une organisation, rangés par offre, sous une racine unique."""

    def __init__(self, root: Path | str | None = None) -> None:
        raw = Path(root or settings.HR_STORAGE_DIR)
        # Un chemin relatif est ancré sur backend/, pas sur le cwd du processus
        # (l'API, le worker Celery et les tests ne démarrent pas au même endroit).
        self.root = (raw if raw.is_absolute() else _BACKEND_DIR / raw).resolve()

    def save(self, *, org_id: uuid.UUID, job_id: uuid.UUID, data: bytes, kind: str) -> str:
        """Écrit le fichier et renvoie son chemin relatif (celui stocké en base)."""
        suffix, _ = ALLOWED_KINDS[kind]
        relative = f"{org_id}/{job_id}/{uuid.uuid4()}{suffix}"
        target = self.root / relative
        self._ensure_private_dir(target.parent)
        target.write_bytes(data)
        target.chmod(0o600)
        return relative

    def _ensure_private_dir(self, directory: Path) -> None:
        """Crée l'arborescence en 0700 à CHAQUE niveau.

        `mkdir(parents=True, mode=...)` n'applique le mode qu'au dernier
        dossier : les niveaux intermédiaires hériteraient de l'umask (775 sur
        Ubuntu), et un autre compte de la machine pourrait alors énumérer les
        organisations et les offres. Les CV sont des données personnelles :
        ni les fichiers, ni les chemins ne regardent les autres comptes.
        """
        directory.mkdir(parents=True, exist_ok=True)
        current = directory
        while True:
            current.chmod(0o700)
            if current == self.root:
                break
            current = current.parent

    def open(self, relative_path: str) -> BinaryIO:
        return self._resolve(relative_path).open("rb")

    def delete(self, relative_path: str) -> None:
        """Suppression idempotente (un fichier déjà absent n'est pas une erreur)."""
        self._resolve(relative_path).unlink(missing_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        """Chemin absolu, en refusant toute sortie de la racine (`..`, absolu)."""
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Chemin hors du stockage")
        return candidate


_store: FileStore | None = None


def get_file_store() -> FileStore:
    """Instance partagée (surchargeable dans les tests par injection FastAPI)."""
    global _store
    if _store is None:
        _store = FileStore()
    return _store
