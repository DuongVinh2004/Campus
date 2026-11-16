"""Compose only an explicitly provisioned learning store, separate from existing data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from campus247.infrastructure.identity.local_learning import (
    LocalLearningIdentityAdapter,
)

LEARNING_REVISIONS = ("0023", "0024", "0025", "0026", "0027", "0028", "0029", "0030", "0031")


def checked_learning_path(path: Path, workspace: Path) -> Path:
    workspace = workspace.resolve(strict=True)
    absolute = Path(path).absolute()
    if ".." in absolute.parts or not absolute.is_relative_to(workspace):
        raise ValueError("Learning path must have an unambiguous workspace location")
    resolved = absolute.resolve(strict=True)
    if resolved == workspace or not resolved.is_relative_to(workspace):
        raise ValueError("Learning path outside workspace")
    cursor = absolute
    while cursor != workspace:
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("Learning reparse points are not allowed")
        cursor = cursor.parent
    return resolved


def learning_offering_ids(config, field):
    ids = config.get(field, [])
    if isinstance(ids, list):
        try:
            if all(isinstance(value, str) and str(UUID(value)) == value for value in ids):
                return ids
        except ValueError:
            pass
    raise ValueError(f"{field} requires canonical offering IDs")


def load_local_learning(config_path: Path, *, workspace: Path, tenant_id: str,
                        postgres_pool=None, verified_database_name: str | None = None,
                        verified_schema_revision: str | None = None):
    """Missing default config disables the feature; a configured but invalid store fails closed."""
    config_path = checked_learning_path(config_path, workspace)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (config.get("schema") != "local-learning-runtime-v1" or config.get("tenant_id") != tenant_id
        or config.get("synthetic_only") is not True or config.get("storage") not in {"sqlite", "postgres"}):
        raise ValueError("Local learning runtime configuration mismatch")
    paths = {}
    required_paths = ["identity_file", "blob_directory"]
    if config["storage"] == "sqlite":
        required_paths.append("database_file")
    for field in required_paths:
        relative = Path(config[field])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Learning configuration paths must be local relative paths")
        paths[field] = checked_learning_path(config_path.parent / relative, workspace)
    adapter = LocalLearningIdentityAdapter(paths["identity_file"], tenant_id)
    directory = adapter.directory()
    from campus247.application.learning.service import LearningService
    from campus247.infrastructure.learning.blob import (
        ClamAVScanner,
        FixtureHashScanner,
        LearningBlobStore,
        UnavailableScanner,
    )
    from campus247.infrastructure.learning.repository import (
        PostgresLearningRepository,
        SQLiteLearningRepository,
    )
    feedback_offerings = learning_offering_ids(config, "page_feedback_offerings")
    version_change_offerings = learning_offering_ids(config, "version_change_offerings")
    exit_ticket_offerings = learning_offering_ids(config, "exit_ticket_offerings")
    idea_card_offerings = learning_offering_ids(config, "idea_card_offerings")
    accessible_text_offerings = learning_offering_ids(config, "accessible_text_offerings")
    ocr_paused_offerings = learning_offering_ids(config, "accessible_text_ocr_paused_offerings")
    if not set(ocr_paused_offerings).issubset(accessible_text_offerings):
        raise ValueError("accessible_text_ocr_paused_offerings must also be enabled for accessible text")
    ocr_quota = config.get("accessible_text_byte_quota", 12 * 1024**3)
    if type(ocr_quota) is not int or not 0 < ocr_quota <= 64 * 1024**3:
        raise ValueError("Accessible text requires a positive configured byte quota")

    def schema_has(revision):
        return verified_schema_revision in LEARNING_REVISIONS[LEARNING_REVISIONS.index(revision):]

    if config["storage"] == "sqlite":
        repository = SQLiteLearningRepository(paths["database_file"], workspace=workspace, tenant_id=tenant_id)
    else:
        if postgres_pool is None or not verified_database_name or config.get("database_name") != verified_database_name:
            raise ValueError("Learning PostgreSQL requires an explicitly verified matching database")
        # Migration and tenant provisioning are separate explicit operations; never auto-create or fallback.
        for offerings, revision, feature in (
            (feedback_offerings, "0026", "Page feedback"), (version_change_offerings, "0028", "Version changes"),
            (exit_ticket_offerings, "0029", "Exit tickets"), (idea_card_offerings, "0030", "Idea cards"),
            (accessible_text_offerings, "0031", "Accessible text"),
        ):
            if offerings and not schema_has(revision):
                raise ValueError(f"{feature} requires explicitly verified schema revision {revision} or a supported successor")
        repository = PostgresLearningRepository(
            postgres_pool, tenant_id=tenant_id, page_feedback_schema=schema_has("0026"),
            page_explanations_schema=schema_has("0027"), version_changes_schema=schema_has("0028"),
            exit_tickets_schema=schema_has("0029"), idea_cards_schema=schema_has("0030"),
            accessible_text_schema=schema_has("0031"),
        )
    blob_store = LearningBlobStore(paths["blob_directory"], workspace=workspace,
        max_total_bytes=config.get('storage_quota_bytes', 10 * 1024**3))
    optimize_pdf = config.get('pdf_web_view', False)
    if type(optimize_pdf) is not bool:
        raise ValueError('pdf_web_view must be a boolean')
    if optimize_pdf and config['storage'] == 'postgres' and not schema_has("0024"):
        raise ValueError('PostgreSQL PDF views require explicitly verified schema revision 0024 or a supported successor')
    hashes = config.get("synthetic_fixture_sha256", [])
    if not isinstance(hashes, list) or any(not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes):
        raise ValueError("Invalid fixture checksum allowlist")
    ai_hashes = config.get("ai_synthetic_source_sha256", [])
    if not isinstance(ai_hashes, list) or any(not isinstance(h, str) or h not in hashes for h in ai_hashes):
        raise ValueError("Learning AI sources must be explicitly listed synthetic fixture hashes")
    scanner_mode = config.get("scanner_mode", "fixture" if hashes else "unavailable")
    if scanner_mode == "clamav":
        scanner_paths = {}
        for field in ("scanner_executable", "scanner_database_dir", "scanner_temporary_dir", "scanner_cvd_certs_dir"):
            relative = Path(config[field])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Scanner paths must be explicit workspace-relative paths")
            scanner_paths[field] = checked_learning_path(workspace / relative, workspace)
        with scanner_paths["scanner_executable"].open("rb") as stream:
            actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_hash != config.get("scanner_executable_sha256"):
            raise ValueError("Scanner executable checksum mismatch")
        scanner = ClamAVScanner(scanner_paths["scanner_executable"],
            database_dir=scanner_paths["scanner_database_dir"],
            temporary_dir=scanner_paths["scanner_temporary_dir"],
            cvd_certs_dir=scanner_paths["scanner_cvd_certs_dir"])
    elif scanner_mode == "fixture":
        scanner = FixtureHashScanner(hashes)
    elif scanner_mode == "unavailable":
        scanner = UnavailableScanner()
    else:
        raise ValueError("Unknown learning scanner mode")
    service = LearningService(repository, blob_store, tenant_id=tenant_id,
        signing_key=directory["signing_key"], scanner=scanner, directory=adapter.public_directory,
        ai_source_hashes=ai_hashes, optimize_pdf=optimize_pdf, page_feedback_offerings=feedback_offerings,
        page_explanations_available=config["storage"] == "sqlite" or schema_has("0027"),
        version_change_offerings=version_change_offerings, exit_ticket_offerings=exit_ticket_offerings,
        idea_card_offerings=idea_card_offerings, accessible_text_offerings=accessible_text_offerings,
        accessible_text_ocr_paused_offerings=ocr_paused_offerings,
        accessible_text_byte_quota=ocr_quota)
    pptx = config.get('pptx_converter')
    if pptx is not None:
        if not isinstance(pptx, dict) or type(pptx.get('enabled')) is not bool:
            raise ValueError('Explicit PowerPoint converter configuration required')
        if pptx['enabled']:
            if config['storage'] == 'postgres' and not schema_has("0025"):
                raise ValueError('PowerPoint renditions require explicitly verified schema revision 0025 or a supported successor')
            configure_learning_pptx(service, pptx, workspace=workspace)
    if accessible_text_offerings and (ocr := config.get("accessible_text_runtime")) is not None:
        service.accessible_text_pipeline = configure_learning_ocr(ocr, workspace=workspace, blob_root=paths["blob_directory"])
    return service, adapter


def configure_learning_ocr(config, *, workspace, blob_root):
    """Accept only a pinned offline OCR runtime and a separate scratch root."""
    if not isinstance(config, dict) or config.get("executor") != "wsl-bubblewrap" or not isinstance(config.get("pins"), dict):
        raise ValueError("Accessible text requires the configured isolated OCR executor")
    paths = {}
    for field in ("runtime_root", "work_root"):
        relative = Path(config[field])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("OCR paths must stay within the workspace")
        paths[field] = checked_learning_path(workspace / relative, workspace)
    work_root, runtime_root = paths["work_root"], paths["runtime_root"]
    if any(work_root.is_relative_to(root) or root.is_relative_to(work_root) for root in (blob_root, runtime_root)):
        raise ValueError("OCR scratch must be separate from immutable sources and runtime")
    from campus247_worker.learning.accessible_text import LearningOcrPipeline
    from campus247_worker.learning.ocr_sandbox import WslOcrRunner

    runner = WslOcrRunner(workspace=workspace, runtime_root=runtime_root, pins=config["pins"],
                          distribution=config.get("distribution", "Ubuntu"))
    return LearningOcrPipeline(workspace=workspace, work_root=work_root, runner=runner, language=config.get("language", "vie"))


def configure_learning_pptx(service, config, *, workspace):
    """Accept only an explicit, pinned local runtime with the isolated executor."""
    if config.get('executor') != 'wsl-bubblewrap':
        raise ValueError('PowerPoint requires the configured isolated executor')
    paths = {}
    for field in ('runtime_root', 'output_root', 'runtime_manifest', 'runtime_defaults_manifest'):
        relative = Path(config[field])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('PowerPoint runtime paths must stay within the workspace')
        paths[field] = checked_learning_path(workspace / relative, workspace)
    for field in ('runtime_manifest', 'runtime_defaults_manifest'):
        data = paths[field].read_bytes()
        if hashlib.sha256(data).hexdigest() != config[field + '_sha256']:
            raise ValueError('PowerPoint runtime manifest checksum mismatch')
        manifest = json.loads(data)
        files = manifest['files'] if field == 'runtime_manifest' else manifest
        for name, expected in files.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('PowerPoint dependency path invalid')
            target = checked_learning_path(paths['runtime_root'] / relative, workspace)
            if not target.is_relative_to(paths['runtime_root']):
                raise ValueError('PowerPoint dependency path outside runtime')
            with target.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('PowerPoint runtime dependency checksum mismatch')
    from campus247_worker.learning.pptx import PptxConverter, PptxConverterConfig
    from campus247_worker.learning.wsl_sandbox import WslBubblewrapExecutor
    executor = WslBubblewrapExecutor(workspace=workspace, runtime_root=paths['runtime_root'],
        converter_sha256=config['converter_sha256'], bwrap_sha256=config['bwrap_sha256'], distribution=config['distribution'])
    service.pptx_converter = PptxConverter(PptxConverterConfig(workspace=workspace, output_root=paths['output_root'],
        executable=paths['runtime_root'] / 'usr/lib/libreoffice/program/soffice.bin',
        executable_sha256=config['converter_sha256'], converter_version=config['converter_version']), executor)


def configure_learning_ai(service, gateway, *, enabled: bool):
    """Explicitly attach the existing guarded provider; this does not perform inference."""
    if not enabled:
        return
    if service is None or gateway is None or not callable(getattr(gateway, "generate", None)):
        raise ValueError("Learning AI requires a configured learning store and guarded generation gateway")
    if not service.ai_source_hashes:
        raise ValueError("Learning AI requires explicit synthetic source hashes")
    from campus247.application.learning.explanation import LearningExplanationVerifier
    service.ai_gateway = gateway
    service.ai_verifier = LearningExplanationVerifier(gateway)
