---
title: "artifact-release-protocol — Profilo package-registry"
scope: "Preflight (versione assente su registro npm/pypi/maven), Fase 3 (publish), Fase 5 (verifica dist-tags/metadata). Nessun host privato cablato."
part_of: artifact-release-protocol
---
# Profilo package-registry

Foglia della skill `.claude/skills/artifact-release-protocol.md`.
Prerequisito: boot check completato, variabili `TOKEN`, `PY`, `MAIN_SHA` disponibili.

Costanti dal blocco `release_targets[]`:
- `registry`: URL del registro pacchetti (es. `https://registry.npmjs.org`, `https://pypi.org`,
  `https://repo.maven.apache.org/maven2`, o un registro privato)
- `package_name`: nome del pacchetto (es. `@org/mylib`, `mylib`, `com.example:mylib`)
- `registry_type`: `npm` | `pypi` | `maven`

> Le versioni pubblicate su npm, pypi e maven sono **immutabili** nella quasi totalita'
> dei registri. Il preflight 1b verifica l'assenza prima di procedere. Un secondo tentativo
> di pubblicare la stessa versione produrra' un errore di "conflict" o "already exists".

---

## Preflight 1b — Versione assente sul registro

### npm

```bash
RESP=$(curl -s "${REGISTRY}/${PACKAGE_NAME}" 2>/dev/null)
EXISTS=$(echo "$RESP" | $PY -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('si' if '$VERSION_OR_REF' in d.get('versions', {}) else 'no')
except Exception:
    print('error')
")
case "$EXISTS" in
  si)    echo "STOP 1b: versione '$VERSION_OR_REF' gia' presente su '$REGISTRY'. Immutabile."; exit 1 ;;
  no)    echo "1b OK: versione '$VERSION_OR_REF' non presente." ;;
  error) echo "WARN 1b: verifica registro non conclusiva. Prosegui con cautela." ;;
esac
```

### pypi

```bash
RESP=$(curl -s "${REGISTRY}/pypi/${PACKAGE_NAME}/json" 2>/dev/null)
EXISTS=$(echo "$RESP" | $PY -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('si' if '$VERSION_OR_REF' in d.get('releases', {}) else 'no')
except Exception:
    print('error')
")
# stessa logica di uscita di npm
```

### maven

```bash
# Parsing del group/artifact da package_name (formato: "group:artifact")
MAVEN_GROUP=$(echo "$PACKAGE_NAME" | cut -d: -f1 | tr '.' '/')
MAVEN_ARTIFACT=$(echo "$PACKAGE_NAME" | cut -d: -f2)
MAVEN_URL="${REGISTRY}/${MAVEN_GROUP}/${MAVEN_ARTIFACT}/${VERSION_OR_REF}/${MAVEN_ARTIFACT}-${VERSION_OR_REF}.pom"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$MAVEN_URL")
case "$HTTP_CODE" in
  200) echo "STOP 1b: versione '$VERSION_OR_REF' gia' presente su '$REGISTRY'. Immutabile."; exit 1 ;;
  404) echo "1b OK: versione '$VERSION_OR_REF' non presente." ;;
  *)   echo "WARN 1b: verifica registro non conclusiva (HTTP $HTTP_CODE)." ;;
esac
```

---

## Fase 3 — Pubblicazione pacchetto

> Trigger: solo dopo gate R.14 Fase 2 confermato.
> La pubblicazione avviene via pipeline CI (preferita) o, se `ci_provider: none`, via
> comando locale nel worktree della Fase 1c.

### Pubblicazione via pipeline CI (raccomandato)

Delega alla foglia `ci-providers.md` per il provider dichiarato in `ci_provider`.
La pipeline si occupa dell'autenticazione, del build e del publish sul registro.

### Pubblicazione locale (ci_provider: none)

Solo se esplicitamente dichiarato in config. Eseguita nel worktree della Fase 1c
(SHA immutabile, hooks disabilitati). La skill `worktree-gate` garantisce il cleanup.

**npm:**
```bash
# .npmrc deve contenere //registry:_authToken=$TOKEN gia' configurato
npm publish --registry "$REGISTRY" 2>&1; rc=$?
[ $rc -eq 0 ] || { echo "STOP: npm publish fallito (exit $rc)."; exit $rc; }
```

**pypi (tramite twine):**
```bash
python3 -m build >/dev/null 2>&1
TWINE_PASSWORD="$TOKEN" python3 -m twine upload --repository-url "$REGISTRY" dist/* 2>&1; rc=$?
[ $rc -eq 0 ] || { echo "STOP: twine upload fallito (exit $rc)."; exit $rc; }
```

**maven (tramite mvn deploy):**
```bash
mvn --batch-mode deploy -DskipTests \
  -DaltDeploymentRepository="release::default::$REGISTRY" 2>&1; rc=$?
[ $rc -eq 0 ] || { echo "STOP: mvn deploy fallito (exit $rc)."; exit $rc; }
```

---

## Fase 5 — Verifica presenza sul registro

### npm

```bash
RESP=$(curl -s "${REGISTRY}/${PACKAGE_NAME}")
VER_OK=$(echo "$RESP" | $PY -c "
import json, sys
d = json.load(sys.stdin)
print('si' if '$VERSION_OR_REF' in d.get('versions', {}) else 'no')
")
LATEST=$(echo "$RESP" | $PY -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('dist-tags', {}).get('latest', 'n/d'))
")
echo "npm $PACKAGE_NAME@$VERSION_OR_REF presente: $VER_OK  dist-tags.latest: $LATEST"
```

### pypi

```bash
RESP=$(curl -s "${REGISTRY}/pypi/${PACKAGE_NAME}/json")
VER_OK=$(echo "$RESP" | $PY -c "
import json, sys
d = json.load(sys.stdin)
print('si' if '$VERSION_OR_REF' in d.get('releases', {}) else 'no')
")
echo "pypi $PACKAGE_NAME==$VERSION_OR_REF presente: $VER_OK"
```

### maven

```bash
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "${REGISTRY}/${MAVEN_GROUP}/${MAVEN_ARTIFACT}/${VERSION_OR_REF}/${MAVEN_ARTIFACT}-${VERSION_OR_REF}.pom")
case "$HTTP_CODE" in
  200) echo "maven $PACKAGE_NAME:$VERSION_OR_REF presente: si" ;;
  *)   echo "WARN maven $PACKAGE_NAME:$VERSION_OR_REF non ancora visibile (HTTP $HTTP_CODE)" ;;
esac
```

> La verifica e' best-effort. Se la versione non e' ancora visibile → WARNING (propagazione lenta);
> non STOP. L'entry di log registra il risultato della verifica.
