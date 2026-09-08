"""
Resource handler factory://config — Factory-as-MCP-Server (EP-058, v2.39)
Espone factory.config.yaml filtrato (no env vars, no segreti) come risorsa read-only.

URI scheme:
  factory://config                → factory.config.yaml (con filtro segreti applicato)
  factory://config/pattern-version → valore pattern_version estratto dal file

Filtro segreti (conservativo — preferisce falsi positivi a falsi negativi):
  - Valori che iniziano con '$' → '<REDACTED>'
  - Valori nei campi 'auth_env:' → '<REDACTED>'
  Il filtro è line-based (regex), senza parsing YAML completo.

R.MCP1 (ADR-MCP-002): il file originale NON viene mai modificato. Solo lettura.
"""
from pathlib import Path
import re

# Pattern di redazione (conservative — falsi positivi accettati)
_SECRET_PATTERNS = [
    # Valore che inizia con '$' (env var reference)
    (re.compile(r"(:\s*)(\$\S+)"), r"\1<REDACTED>"),
    # Valore dopo auth_env: (qualsiasi valore)
    (re.compile(r"(auth_env:\s*)(\S+)"), r"\1<REDACTED>"),
]


def _redact_secrets(content: str) -> str:
    """Applica il filtro segreti line-by-line al contenuto YAML."""
    lines = []
    for line in content.splitlines():
        for pattern, replacement in _SECRET_PATTERNS:
            line = pattern.sub(replacement, line)
        lines.append(line)
    return "\n".join(lines)


def register_config_resources(mcp, factory_root: Path) -> None:
    """Registra resource factory://config per factory.config.yaml."""

    config_path = factory_root / "factory.config.yaml"

    @mcp.resource("factory://config")
    def read_factory_config() -> str:
        """Restituisce factory.config.yaml filtrato (segreti redatti).

        Il file originale NON viene modificato (R.MCP1).
        I valori che iniziano con '$' e i campi 'auth_env:' sono sostituiti con '<REDACTED>'.
        """
        if not config_path.exists():
            raise FileNotFoundError(
                f"factory.config.yaml non trovato in FACTORY_ROOT='{factory_root}'. "
                "Verificare che FACTORY_ROOT punti alla directory radice della factory."
            )
        raw = config_path.read_text(encoding="utf-8")
        return _redact_secrets(raw)

    @mcp.resource("factory://config/pattern-version")
    def read_pattern_version() -> str:
        """Restituisce la versione corrente del pattern (pattern_version da factory.config.yaml)."""
        if not config_path.exists():
            raise FileNotFoundError(f"factory.config.yaml non trovato in '{factory_root}'")
        content = config_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("pattern_version:"):
                return line.split(":", 1)[1].strip().strip('"')
        return "(pattern_version non trovata)"
