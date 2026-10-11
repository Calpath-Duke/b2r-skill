# Adapted from K-Dense Inc. scientific-agent-skills (MIT); see THIRD_PARTY_NOTICES.md.
#!/usr/bin/env python3
"""Safe Matplotlib export helpers with explicit, auditable settings.

This module does not certify journal compliance. Publisher profiles are dated
planning snapshots and must be confirmed against the target journal.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

from _common import CliError, checked_output_file, emit_json, positive_float

SCHEMA_VERSION = "1.0"
SUPPORTED_FORMATS = {
    "pdf",
    "svg",
    "eps",
    "ps",
    "png",
    "tiff",
    "jpeg",
    "webp",
}
FORMAT_ALIASES = {"jpg": "jpeg", "tif": "tiff"}
VECTOR_FORMATS = {"pdf", "svg", "eps", "ps"}
RASTER_FORMATS = {"png", "tiff", "jpeg", "webp"}
METADATA_FORMATS = {"pdf", "svg", "png", "eps", "ps"}
MAX_FORMATS = 8


def _normalize_formats(formats: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for item in formats:
        for value in item.split(","):
            raw_name = value.strip().lower().lstrip(".")
            name = FORMAT_ALIASES.get(raw_name, raw_name)
            if not name:
                continue
            if name not in SUPPORTED_FORMATS:
                raise CliError(
                    f"unsupported format {name!r}; "
                    f"available: {', '.join(sorted(SUPPORTED_FORMATS))}"
                )
            if name not in normalized:
                normalized.append(name)
    if not normalized:
        raise CliError("at least one output format is required")
    if len(normalized) > MAX_FORMATS:
        raise CliError(f"at most {MAX_FORMATS} output formats are allowed")
    return normalized


def _base_output_path(value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.suffix.lower().lstrip(".") in SUPPORTED_FORMATS | set(FORMAT_ALIASES):
        path = path.with_suffix("")
    if not path.name:
        raise CliError("output must include a base filename")
    return path


def _font_rc(font_mode: str) -> dict[str, Any]:
    if font_mode == "current":
        return {}
    if font_mode == "truetype":
        return {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            # Editable SVG text; unlike PDF Type 42, this is not embedded.
            "svg.fonttype": "none",
        }
    if font_mode == "paths":
        return {
            "pdf.fonttype": 3,
            "ps.fonttype": 3,
            "svg.fonttype": "path",
        }
    raise CliError("font_mode must be 'truetype', 'paths', or 'current'")


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _atomic_savefig(
    fig: Any,
    destination: Path,
    *,
    format_name: str,
    save_kwargs: dict[str, Any],
    overwrite: bool,
    tiff_rgb: bool = False,
) -> None:
    destination = checked_output_file(destination, force=overwrite)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=f".{format_name}",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        fig.savefig(temporary, format=format_name, **save_kwargs)
        if tiff_rgb and format_name == "tiff":
            from PIL import Image

            with Image.open(temporary) as rendered:
                if "A" in rendered.getbands() and rendered.getchannel("A").getextrema() != (255, 255):
                    raise CliError("RGB TIFF requires an opaque rendered background")
                rgb = rendered.convert("RGB")
                pillow_options = dict(save_kwargs.get("pil_kwargs", {}))
                pillow_options.setdefault("dpi", rendered.info.get("dpi", (save_kwargs["dpi"],) * 2))
                if rendered.info.get("icc_profile"):
                    pillow_options.setdefault("icc_profile", rendered.info["icc_profile"])
            try:
                rgb.save(temporary, format="TIFF", **pillow_options)
            finally:
                rgb.close()
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise CliError(f"Matplotlib produced no data for {destination}")
        if overwrite:
            os.replace(temporary, destination)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise CliError(f"refusing to overwrite existing output: {destination}") from exc
    except CliError:
        raise
    except Exception as exc:
        raise CliError(
            f"failed to export {destination.name} as {format_name}: {exc}"
        ) from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _validate_provenance(provenance: dict[str, Any] | None) -> dict[str, Any]:
    if provenance is None:
        return {}
    if not isinstance(provenance, dict):
        raise CliError("provenance must be a dictionary")
    try:
        encoded = json.dumps(provenance, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CliError(f"provenance must be JSON serializable: {exc}") from exc
    if len(encoded) > 1_000_000:
        raise CliError("provenance metadata is limited to 1,000,000 bytes")
    return provenance


def export_figure(
    fig: Any,
    filename: str | os.PathLike[str],
    *,
    formats: Iterable[str] = ("pdf", "png"),
    dpi: float = 300,
    transparent: bool = False,
    tiff_rgb: bool = False,
    bbox_inches: str | None = None,
    pad_inches: float = 0.1,
    facecolor: str = "white",
    edgecolor: str = "none",
    font_mode: str = "truetype",
    overwrite: bool = False,
    mkdir: bool = False,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    write_manifest: bool = False,
    savefig_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Export a Matplotlib figure atomically with explicit format settings.

    ``dpi`` is passed to vector backends too because it controls rasterized
    artists and embedded raster images. ``bbox_inches=None`` preserves the
    figure's physical page dimensions; use ``"tight"`` only when that change is
    intentional.
    """
    if not (float(dpi) > 0 and math.isfinite(float(dpi))):
        raise CliError("dpi must be finite and greater than zero")
    if not (float(pad_inches) >= 0 and math.isfinite(float(pad_inches))):
        raise CliError("pad_inches must be finite and non-negative")
    normalized_formats = _normalize_formats(formats)
    if tiff_rgb and ("tiff" not in normalized_formats or transparent):
        raise CliError("tiff_rgb requires TIFF output and transparent=False")
    base = _base_output_path(filename)
    parent = base.parent
    if mkdir:
        parent.mkdir(parents=True, exist_ok=True)
    if not parent.exists() or not parent.is_dir():
        raise CliError(f"output parent directory does not exist: {parent}")
    if parent.is_symlink():
        raise CliError(f"output parent must not be a symlink: {parent}")
    for format_name in normalized_formats:
        checked_output_file(
            parent / f"{base.name}.{format_name}",
            force=overwrite,
        )
    if write_manifest:
        checked_output_file(
            parent / f"{base.name}.export.json",
            force=overwrite,
        )

    try:
        import matplotlib as mpl
    except ImportError as exc:
        raise CliError(
            "Matplotlib is required for figure export; "
            "run with --with 'matplotlib==3.11.2'"
        ) from exc

    provenance_document = _validate_provenance(provenance)
    user_metadata = dict(metadata or {})
    creator = user_metadata.setdefault(
        "Creator",
        f"scientific-visualization figure_export.py; Matplotlib {mpl.__version__}",
    )
    if not isinstance(creator, str):
        raise CliError("metadata Creator must be a string")
    extra_kwargs = dict(savefig_kwargs or {})
    if "format" in extra_kwargs:
        raise CliError("savefig_kwargs must not override format")
    protected = {
        "dpi",
        "transparent",
        "bbox_inches",
        "pad_inches",
        "facecolor",
        "edgecolor",
        "metadata",
    }
    overlap = protected.intersection(extra_kwargs)
    if overlap:
        raise CliError(
            "savefig_kwargs must not override explicit settings: "
            + ", ".join(sorted(overlap))
        )

    figure_size = [float(value) for value in fig.get_size_inches()]
    outputs: list[dict[str, Any]] = []
    warnings_list: list[str] = []
    export_rc = _font_rc(font_mode)
    if bbox_inches is None:
        # Prevent a user's global savefig.bbox="tight" from changing page size.
        export_rc["savefig.bbox"] = None
    with mpl.rc_context(export_rc):
        for format_name in normalized_formats:
            destination = parent / f"{base.name}.{format_name}"
            checked_output_file(destination, force=overwrite)
            if format_name in {"eps", "ps"}:
                format_metadata = {"Creator": user_metadata["Creator"]}
            elif format_name in METADATA_FORMATS:
                format_metadata = dict(user_metadata)
                if format_name == "svg":
                    format_metadata["Date"] = "2026-01-01"
                elif format_name == "pdf":
                    format_metadata["CreationDate"] = None
                    format_metadata["ModDate"] = None
            else:
                format_metadata = None
            if user_metadata and format_name not in METADATA_FORMATS:
                warnings_list.append(
                    f"{format_name}: Matplotlib does not support savefig metadata "
                    "for this format; metadata remains in the optional manifest."
                )
            save_kwargs: dict[str, Any] = {
                "dpi": float(dpi),
                "transparent": transparent,
                "bbox_inches": bbox_inches,
                "pad_inches": float(pad_inches),
                "facecolor": "none" if transparent else facecolor,
                "edgecolor": "none" if transparent else edgecolor,
                **extra_kwargs,
            }
            if format_metadata is not None:
                save_kwargs["metadata"] = format_metadata
            if format_name == "tiff":
                save_kwargs["pil_kwargs"] = {
                    **save_kwargs.get("pil_kwargs", {}),
                    "compression": "tiff_lzw",
                }

            _atomic_savefig(
                fig,
                destination,
                format_name=format_name,
                save_kwargs=save_kwargs,
                overwrite=overwrite,
                tiff_rgb=tiff_rgb,
            )
            outputs.append(
                {
                    "path": str(destination.resolve()),
                    "format": format_name,
                    "kind": (
                        "vector-container"
                        if format_name in VECTOR_FORMATS
                        else "raster"
                    ),
                    "size_bytes": destination.stat().st_size,
                }
            )

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "outputs": outputs,
        "settings": {
            "formats": normalized_formats,
            "dpi": float(dpi),
            "transparent": transparent,
            "tiff_rgb": tiff_rgb,
            "bbox_inches": bbox_inches,
            "pad_inches": float(pad_inches),
            "facecolor": facecolor,
            "font_mode": font_mode,
            "figure_size_inches": figure_size,
        },
        "versions": {
            "matplotlib": mpl.__version__,
            "pillow": _package_version("Pillow"),
        },
        "provenance": provenance_document,
        "warnings": sorted(set(warnings_list)),
        "notice": (
            "Export completed with explicit settings. This report does not "
            "establish visual, accessibility, scientific-integrity, or "
            "journal-submission compliance."
        ),
    }

    if write_manifest:
        manifest_path = parent / f"{base.name}.export.json"
        emit_json(report, output=manifest_path, force=overwrite)
        report["manifest"] = str(manifest_path.resolve())
    return report


