# shell-portability — Windows: WSL2 e diagnosi dell'antivirus

Ambito: due procedure per chi lavora con la factory su Windows e trova le sessioni lente.
Si consulta da `shell-portability.md` §Prestazioni. Le esegue l'operatore sulla propria
postazione: nessun agente installa software, cambia configurazioni di sistema o contatta l'IT.

Punto di partenza, due serie di misure su Windows 11 (mediane, ms).

- **Git Bash, 7 report su una derivata (2026-09-25):** un processo vuoto costa 289-548, contro
  20-40 di una Git Bash in salute e 1-3 su Linux.
- **Lanci nativi da PowerShell, una postazione (2026-10-12, mediana di 7):** `cmd /c exit` 164,
  `git --version` 147, `bash -c true` 323, Python gestito da uv 229, Python dell'alias
  Microsoft Store 716 netti, Node 485-560 (max 1281). Una lettura di file in-process: 0,22.

Il costo è per processo, non per byte, **e non è proprio di Git Bash**: anche i lanci nativi lo
pagano, quindi uscire da Git Bash non basta da solo. La causa **non è provata**:
l'antivirus/EDR in real-time è l'ipotesi principale (Defender attivo in tempo reale sulla
postazione nativa), ma nessuno ha misurato con lo scanner escluso. Queste procedure servono a
raccogliere i dati, non a confermarla.

**Python: gestito da uv, o l'installer di python.org; non l'alias del Microsoft Store.** Sulla
postazione misurata l'alias costa circa 490 ms in più a ogni avvio. Verifica con
`where python`: un percorso sotto `WindowsApps` è l'alias. Stima (aritmetica sulle mediane, non
una misura): un hook `bash` che lancia Python costa almeno ~550 ms con Python uv, ~1 s con quello
dello Store.

---

## Misura di riferimento

Prima e dopo ogni intervento, nella root della factory e con **una sola** sessione di lavoro
aperta (le misure parallele erano il difetto principale dei report):

```bash
s=$(date +%s%N); for i in $(seq 1 10); do /usr/bin/true; done; e=$(date +%s%N)
echo "$(( (e-s)/10000000 )) ms per processo"
time git status --short --ignore-submodules=none >/dev/null   # scende in ogni submodule
time git status --short >/dev/null                            # con ignore = dirty (lint 4ax)
tasklist | grep -icE 'node.exe|claude'; tasklist | grep -ic 'git.exe'   # processi concorrenti (Git Bash)
```

Lanci nativi, da PowerShell (stessa forma: mediana di 7, processi concorrenti contati):

```powershell
function Med($c){ $t=1..7|%{ (Measure-Command{ & cmd /c $c }).TotalMilliseconds }|sort; $t[3] }
"cmd /c exit : $(Med 'exit') ms"; "python -c 0 : $(Med 'python -c 0') ms"; "node -e 0 : $(Med 'node -e 0') ms"
(Get-Process node,claude,git -ea 0).Count   # processi concorrenti
```

Il lancio via `cmd /c` aggiunge il costo di `cmd`: sottrai la riga `cmd /c exit` per il netto.

---

## A. WSL2 con il repo in `~/`

È l'ambiente raccomandato da `shell-portability.md`. In WSL2 i processi si creano in modo nativo
Linux e non passano dall'emulazione `fork()` di Git Bash (MSYS), che nei report fallisce con
`Win32 error 5`. Quanto l'antivirus pesi anche dentro WSL2 non è misurato: lo dice la misura di
riferimento eseguita nel terminale WSL.

### A.1 Prerequisiti

- Windows 11 con virtualizzazione attiva. Su un portatile gestito WSL può essere disabilitato
  da policy: se `wsl --install` fallisce per permessi, la richiesta va all'IT.
- RAM: WSL2 è una VM. Sui PC poco potenti limitane la memoria (A.3).

### A.2 Installazione

Da PowerShell **come amministratore**:

```powershell
wsl --install -d Ubuntu
wsl -l -v          # la colonna VERSION deve dire 2
```

Riavvia se richiesto, apri **Ubuntu** dal menu Start e crea l'utente Linux.

### A.3 Limiti di risorse (PC poco potenti)

File `%UserProfile%\.wslconfig` su Windows, poi `wsl --shutdown` per applicarlo:

```ini
[wsl2]
memory=4GB
processors=2
# se dietro la VPN aziendale i nomi non si risolvono dentro WSL:
# networkingMode=mirrored
# dnsTunneling=true
```

I valori sono un punto di partenza: alzali se build o test vanno in swap.

### A.4 Strumenti e Git

Nel terminale Ubuntu:

```bash
sudo apt update && sudo apt install -y git python3 python3-yaml curl
git config --global user.name  "<nome come sull'host remoto>"
git config --global user.email "<email>"
git config --global core.autocrlf input
```

Node con nvm, alla versione dei `.nvmrc` dei repo (verifica con `/init-check`, blocco `environment:`).

### A.5 Clone in `~/`, mai in `/mnt/c/`

```bash
mkdir -p ~/repos && cd ~/repos
git clone <url-della-factory> <factory>
cd <factory>
git submodule update --init <path-del-submodule>   # solo i submodule che usi
```

`/mnt/c/` è il disco Windows visto attraverso un file system di rete: ogni accesso attraversa
il confine VM-Windows, e lì valgono le lentezze di NTFS. Non inizializzare tutti i submodule
se non servono. Credenziali e file `.env` si configurano come su Windows (`/init-check`, blocco
`environment:`).

### A.6 VS Code e Claude Code

Installa su Windows l'estensione **WSL** di Microsoft, poi dal terminale Ubuntu:

```bash
cd ~/repos/<factory> && code .
```

VS Code si riapre "dentro" WSL (indicatore in basso a sinistra). L'estensione Claude Code va
installata anche nel lato WSL quando VS Code lo propone.

### A.7 Verifica

Ripeti la misura di riferimento nel terminale WSL. Atteso, se l'ambiente è sano: pochi ms per
processo e `git status --short` sotto il secondo. Registra il risultato come fonte in `raw/`
(prima e dopo), cosi' la diagnosi resta verificabile.

---

## B. Diagnosi dell'antivirus, prima di qualsiasi richiesta all'IT

Scopo: arrivare dall'IT con dati, non con un sospetto: prima il test, poi la richiesta. Nessun passo di questa
sezione cambia configurazioni: si legge soltanto.

### B.1 Sintomo riproducibile in Git Bash

```bash
echo "sostituzione di comando: $(git submodule status | wc -l)"
git submodule status | wc -l
```

Nei report della derivata la prima riga stampava `0` con `open_setup failed, Win32 error 5` e la
seconda il numero vero di submodule. Annota se si ripete: è il segno di una creazione di processo negata, non di una lentezza.

### B.2 Filtri sul file system

Prompt dei comandi o PowerShell **come amministratore**:

```powershell
fltmc filters
```

Elenca i minifilter caricati. `WdFilter` è Microsoft Defender; gli altri nomi vanno identificati
con l'IT. Salva l'output completo.

### B.3 Stato di Microsoft Defender

```powershell
Get-MpComputerStatus | Select-Object AMRunningMode, RealTimeProtectionEnabled
Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
```

`AMRunningMode` dice se Defender è l'antivirus attivo (`Normal`) o in modalità passiva accanto
a un altro prodotto. La lista delle esclusioni senza privilegi di amministratore può risultare
nascosta: annotalo invece di dedurne che è vuota.

### B.4 Cosa portare all'IT

1. Misura di riferimento (sopra), con il conteggio dei processi concorrenti.
2. Output di B.1, B.2 e B.3.
3. Le opzioni, dalla meno alla più invasiva per la copertura antivirus:
   - **Dev Drive**: volume ReFS dedicato al codice (Windows 11, build recenti). Con Defender
     come antivirus attivo abilita la "modalità prestazioni", che sposta la scansione in
     asincrono invece di toglierla; l'amministratore può anche limitare i filtri che si
     agganciano al volume (`fsutil devdrv`). Richiede privilegi di amministratore, può essere
     disabilitato da policy e chiede almeno 50 GB liberi.
   - **Esclusione della cartella dei repo** dalla scansione in real-time: è l'intervento con il
     guadagno potenziale più alto, e anche quello che toglie più copertura.

Se l'IT concede un intervento, rifai la misura di riferimento: sotto i 40 ms per processo
l'ipotesi antivirus è confermata; se non cambia, è falsificata e va scritto nella nuova misura.

[^src: backport da una derivata (EP-072), misure su Windows 11 del 2026-09-25]
