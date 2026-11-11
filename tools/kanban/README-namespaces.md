---
type: tool-readme
status: approved
tags: [kanban, tooling, namespace, multi-repo]
ingest_eligible: true
---

# Runbook — Registro dei namespace kanban (EP-069 US-314)

## Quando serve

Il kanban della factory master usa un namespace unico senza prefisso (`TSK-720`, `US-314`,
`EP-069`). La capability descritta in questo runbook serve alle **factory derivate** con
piu' `code_path` separati, dove assegnare a ciascun repo un prefisso di namespace distinto
previene collisioni tra sessioni parallele.

**Segnale pratico**: se la tua factory ha 2+ `code_path` con kanban separati e le epiche
vengono lavorate in parallelo da piu' agenti o persone, attiva i namespace.

La convenzione che governa questa scelta e' **C-004** (un prefisso = un `code_path`),
documentata in `management/conventions.md`. Questo runbook ne e' la parte operativa.

---

## Componenti

| Componente | Percorso | Ruolo |
|---|---|---|
| Registro YAML | `management/kanban/id-registry.yaml` | Fonte di verita': namespace e prenotazioni |
| Config gate | `factory.config.yaml` § `kanban_namespaces` | Abilita la capability (default: off) |
| CLI next-id | `tools/kanban/next-id.py --namespace <PREFIX>` | Prossimo ID libero con rispetto prenotazioni |
| Checker collisioni | `tools/kanban/id_registry_check.py` | Collisioni, range sovrapposti, stale |
| Indice inverso | `tools/kanban/namespace_orphans.py` | Task sotto prefisso estraneo (C-004) |
| Test | `tests/test_kanban_namespaces.py` | 14 test unitari + non-regressione |

---

## Abilitare la capability

```yaml
# factory.config.yaml
kanban_namespaces:
  enabled: true
  registry: management/kanban/id-registry.yaml
```

A flag spento (`enabled: false`, default), `next-id.py` si comporta come prima di US-314
e il registro viene ignorato anche se presente su disco.

---

## Schema del registro

```yaml
# management/kanban/id-registry.yaml

namespaces:
  - prefix: "UP"                              # stringa maiuscola 2-4 lettere
    code_path: "code_repos/portale-upgrade"   # relativo alla root del repo
    description: "portale-upgrade — task atomici"

  - prefix: "FAC"
    code_path: "."
    description: "factory meta-task (governance, tooling, docs)"

reservations:
  - prefix: "UP"      # namespace di riferimento
    kind: "tsk"       # "tsk" | "us" | "ep"
    from: 1           # primo ID del range (inclusivo)
    to: 10            # ultimo ID del range (inclusivo)
    epic: "EP-001"    # epica che ha prenotato il range
    reserved_at: "2026-10-01"   # data ISO 8601
```

**Perche' la mappa prefix->code_path vive nel registro e non in config**:
le prenotazioni cambiano a ogni taskify e richiedono un commit di prenotazione prima di
creare i file TSK (R.21). Tenere mappa e prenotazioni nello stesso file mantiene
l'operazione atomica e riduce il rischio di merge conflict in sessioni parallele.

---

## Come prenotare un range prima del taskify

Questo protocollo implementa R.21 per i namespace, analogo a quanto la factory derivata
portale-servizi-factory usa per prevenire le collisioni UP-TSK-508 e UP-TSK-543.

```bash
# 1. Leggi il registro — find il piu' alto `to` per il tuo namespace+kind
python3 tools/kanban/id_registry_check.py

# 2. Aggiungi la prenotazione nel registro PRIMA di creare i file TSK
#    (es. il prossimo range libero e' 21..30)
# Edita management/kanban/id-registry.yaml:
#   reservations:
#     - prefix: "UP"
#       kind: "tsk"
#       from: 21
#       to: 30
#       epic: "EP-003"
#       reserved_at: "2026-10-05"

# 3. Committa la prenotazione
git add management/kanban/id-registry.yaml
git commit -m "chore(kanban): prenota UP-TSK-021..030 per EP-003"

# 4. Ora crea i file TSK
python3 tools/kanban/next-id.py tsk 10 --namespace UP
# → UP-TSK-021, UP-TSK-022, ... UP-TSK-030
```

---

## Come generalizza la convenzione C-004

**C-004**: un prefisso namespace mappa uno e un solo `code_path`.

In una factory a namespace singolo (come il master) la convenzione e' garantita
trivialmente: non ci sono prefissi. In una factory con N `code_path`:

- Ogni repo dichiarato in `factory.config.yaml#code_paths[]` riceve un prefisso
  registrato in `id-registry.yaml#namespaces`.
- Il TPM usa `--namespace <PREFIX>` per allocare ID nel namespace corretto.
- `namespace_orphans.py` verifica che task aperti non insistano su un repo con un
  prefisso estraneo (eccezione: epiche di migrazione con `migration_epic: true`,
  coperte da C-004.1).

---

## Comandi di diagnostica

```bash
# Collisioni, stale, range sovrapposti
python3 tools/kanban/id_registry_check.py

# Stessi check con exit 1 su fail (per CI)
python3 tools/kanban/id_registry_check.py --check

# Indice inverso: task sotto prefisso estraneo
python3 tools/kanban/namespace_orphans.py

# Sezione markdown per sprint.md
python3 tools/kanban/namespace_orphans.py --markdown

# Prossimo ID libero (senza namespace — factory master)
python3 tools/kanban/next-id.py tsk

# Prossimo ID libero con namespace (factory derivata)
python3 tools/kanban/next-id.py tsk --namespace UP
python3 tools/kanban/next-id.py us 5 --namespace FAC
```

---

## Checklist post-taskify

- [ ] Il registro ha una prenotazione per il range allocato.
- [ ] `python3 tools/kanban/id_registry_check.py --check` esce con 0.
- [ ] `python3 tools/kanban/namespace_orphans.py --check` esce con 0.
- [ ] I file TSK creati hanno il prefisso corretto per il loro `code_path`.
