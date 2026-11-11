"""Lettura dei path dei registri e del kanban dal blocco engineering_practices di factory.config.yaml."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULTS = {"kanban_path": "management/kanban", "analytics_path": "analytics/pocock-pilota"}


def settings(root=ROOT):
    """Valori di engineering_practices.{kanban_path,analytics_path}; default se config o chiavi mancano."""
    out = dict(DEFAULTS)
    cfg = pathlib.Path(root) / "factory.config.yaml"
    if cfg.is_file():
        try:
            import yaml
            block = (yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}).get("engineering_practices") or {}
            for k in out:
                if block.get(k):
                    out[k] = str(block[k])
        except Exception:
            pass
    return out
