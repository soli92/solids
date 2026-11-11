"""Prompt di verifica per le voci del report PM (pulsante «Chiedi una verifica»).

Sono template riempiti con i dati della misura: nessun testo è prodotto da un modello. Il prompt va incollato in una sessione
Claude nella factory. Indica lo strumento della factory che fa la verifica (in sola lettura) e quello che fa l'eventuale modifica
o riconciliazione, che parte solo dopo la conferma del coordinatore.
"""

# Strumenti indicati nei prompt. I default puntano agli strumenti di questa factory; una factory
# con strumenti diversi li sostituisce in config (`prompt_verifica.strumenti`, `prompt_verifica.modifica`,
# `prompt_verifica.fonti_esterne`), senza toccare il codice: vedi configura().
TPM = ('agente `tpm` della factory (.claude/agents/tpm.md): aggiornamento non distruttivo del TSK '
       '(nota datata, status motivato); prima di scrivere controlla i claim advisory del cooperative locking (EP-053) con '
       '`python3 tools/session/active_sessions.py conflicts --domain management/kanban`; non tocca i TSK che un dev sta lavorando oggi')
STRUMENTI_DEFAULT = {
    'chiuso_senza_esito': {
        'verifica': 'git log -p sul file del TSK per trovare il commit della transizione di status (autore, data, messaggio); '
                    'lettura dei file dei successori (superseded_by o TSK citati nelle note) per verificarne esistenza e stato; '
                    'controllo a mano dei campi di chiusura nel frontmatter (superseded_by, superseded_at, superseded_reason, closed_at, resolution), '
                    'che il report segnala già come «chiusura senza metadati» se mancano'},
    'sospeso': {
        'verifica': 'git log -p sul file del TSK per il commit che lo ha messo on_hold/deferred (data, autore, motivo) e lettura della nota datata; '
                    'Check 4g di .claude/skills/lint-checks-kanban.md per i blocked_by verso question'},
    'bloccato': {
        'verifica': 'Check 4g «Coerenza scheduler/depends_on» di .claude/skills/lint-checks-kanban.md (blocked_by, depends_on); '
                    'git log -p sul file del TSK per il commit che lo ha bloccato'},
    'sconosciuto': {
        'verifica': 'Check 3 «Integrità kanban» di .claude/skills/lint-checks-kanban.md (campi obbligatori e valori ammessi)'},
    'in_attesa_prerequisito_aperto': {
        'verifica': 'Check 4g «Coerenza scheduler/depends_on» di .claude/skills/lint-checks-kanban.md; '
                    'procedura .claude/skills/tpm-reconcile.md, passo 3 (dipendenze insoddisfatte e drift temporale), applicata ai '
                    'prerequisiti per vedere se il loro status è indietro rispetto ai commit'},
    'prerequisito_da_riconciliare': {
        'verifica': 'Check 4g «Coerenza scheduler/depends_on» di .claude/skills/lint-checks-kanban.md (dipendenze verso TSK chiusi o sostituiti)'},
    'prerequisito_fuori_perimetro': {
        'verifica': 'Check 4g «Coerenza scheduler/depends_on» di .claude/skills/lint-checks-kanban.md (dipendenze orfane); '
                    '`python3 tools/kanban/id_registry_check.py --markdown` per l\'esistenza dell\'ID'},
    'sezione_vuota': {
        'verifica': 'lettura della US di sezione e della sua epica; Glob dei TSK nella cartella della US e '
                    'Grep dell\'ID della US in tutto il kanban per trovare TSK collegati da altre US (campo story/us del frontmatter). '
                    'NB: la foglia check-4au.md salta le US senza TSK, qui non serve',
        'modifica': 'agente `tpm` della factory (.claude/agents/tpm.md) per la taskificazione, con gli ID allocati dal registro del kanban '
                    '(`python3 tools/kanban/id_registry_check.py --markdown` per verificarlo)'},
    'rollup': {
        'verifica': 'foglia .claude/skills/references/lint-checks-agent-fleet/check-4au.md (roll-up TSK → US → epica, algoritmo in Python)'},
    'esito_corpo': {
        'verifica': 'lettura della riga citata nel file della US o dell\'epica e del frontmatter del TSK; '
                    'git log -p su entrambi i file per vedere quale dei due è stato aggiornato per ultimo e con quale motivazione. '
                    'Fonte dello stato è il frontmatter del TSK: la riga del corpo è una nota storica, che va rettificata con una nuova nota datata, mai riscritta'},
    'qualita': {
        'verifica': '`python3 tools/kanban/id_registry_check.py --markdown` e `python3 tools/kanban/namespace_orphans.py --markdown` (sola lettura); '
                    'Check 3 «Integrità kanban» di .claude/skills/lint-checks-kanban.md'},
}
FONTI_ESTERNE = 'registri di pacchetti, tracker esterni, persone'
STRUMENTI = {}


def configura(pv_cfg=None):
    """Strumenti dei prompt: default della factory, sovrascritti dalla config `prompt_verifica` (opzionale).
    `modifica` sostituisce lo strumento di modifica di default (tpm); `strumenti.<chiave>.{verifica,modifica}` una voce;
    `fonti_esterne` l'elenco delle fonti fuori dalla factory citate in NON VERIFICABILE."""
    global FONTI_ESTERNE
    pv_cfg = pv_cfg or {}
    modifica = pv_cfg.get('modifica') or TPM
    STRUMENTI.clear()
    for k, v in STRUMENTI_DEFAULT.items():
        STRUMENTI[k] = {'verifica': v['verifica'], 'modifica': v.get('modifica') or modifica}
    for k, v in (pv_cfg.get('strumenti') or {}).items():
        STRUMENTI.setdefault(k, {'verifica': '', 'modifica': modifica}).update({x: y for x, y in v.items() if x in ('verifica', 'modifica') and y})
    FONTI_ESTERNE = pv_cfg.get('fonti_esterne') or 'registri di pacchetti, tracker esterni, persone'
    STANDARD_VERIFICA[4] = _riga_non_verificabile()


DOMANDE = {
    'chiuso_senza_esito': [
        'la chiusura è motivata nel TSK (nota datata, campo superseded_by, decisione citata)?',
        'il lavoro è stato ripreso da un altro TSK? Quale, ed esiste davvero?',
        'lo stato è ancora corretto oggi, o il lavoro va riaperto o contato altrove?',
        'la US e l\'epica padre riportano lo stesso esito (campi come progress, note datate, criteri di accettazione)? '
        'Se no, indica file e riga della dichiarazione discordante.',
    ],
    'sospeso': [
        'perché è sospeso e da quando (fonte)?',
        'cosa serve per riprenderlo, e la condizione è ancora vera?',
    ],
    'bloccato': [
        'cosa lo blocca (TSK, question, decisione o rilascio esterno), con fonte?',
        'il blocco è ancora vero oggi?',
    ],
    'sconosciuto': [
        'lo status non è tra i valori previsti: qual è lo stato reale del lavoro?',
        'quale valore canonico va usato (todo, in_progress, done, superseded, cancelled, on_hold, blocked)?',
    ],
    'in_attesa_prerequisito_aperto': [
        'la dipendenza è ancora necessaria?',
        'lo stato del prerequisito è aggiornato rispetto ai commit e alle note più recenti?',
    ],
    'prerequisito_da_riconciliare': [
        'il prerequisito è superato o annullato: quale TSK lo sostituisce?',
        'la dipendenza va spostata sul TSK sostitutivo o rimossa?',
    ],
    'prerequisito_fuori_perimetro': [
        'il prerequisito esiste? In quale epica?',
        'va aggiunto al perimetro del report, o la dipendenza è sbagliata?',
    ],
}

DESCRIZIONE = {
    'chiuso_senza_esito': 'TSK chiusi senza esito (superati, annullati, rinominati, scartati), esclusi dal calcolo dell\'avanzamento',
    'sospeso': 'TSK sospesi', 'bloccato': 'TSK bloccati', 'sconosciuto': 'TSK con uno status non riconosciuto',
    'in_attesa_prerequisito_aperto': 'TSK aperti che attendono un prerequisito non ancora completato',
    'prerequisito_da_riconciliare': 'TSK aperti il cui prerequisito è stato superato o annullato',
    'prerequisito_fuori_perimetro': 'TSK aperti con un prerequisito assente dal perimetro del report',
}


STANDARD_VERIFICA = [
    '',
    'Standard di verifica: il mandato serve a togliere ogni dubbio sui fatti. Ogni affermazione della tabella ha uno di questi esiti:',
    '- VERIFICATO: con la fonte esatta (file e riga, commit, oppure il comando eseguito e il suo risultato);',
    "- NON TROVATO: hai cercato e la cosa non c'è; indica dove hai cercato e con quali comandi (es. grep su management/kanban/ e wiki/);",
    '',  # riga NON VERIFICABILE: la scrive configura(), con le fonti esterne della config
    'Non usare NON VERIFICABILE per fatti che stanno nei file della factory: se servono più letture (altre US, altri TSK, il git log), falle. '
    'Se un fatto dovrebbe essere nei file della factory e non c\'è traccia, l\'esito è NON TROVATO, non NON VERIFICABILE.',
    'Non dedurre e non riportare come fatto ciò che non hai visto. Cita sempre gli ID con una sintesi tra parentesi.',
]


def _riga_non_verificabile():
    return ('- NON VERIFICABILE: solo se la fonte è fuori dalla factory e non raggiungibile da qui (%s); '
            'indica quale fonte servirebbe.' % FONTI_ESTERNE)


STANDARD_VERIFICA[4] = _riga_non_verificabile()
configura()


def _testa(ctx, voce, descrizione, chiave):
    s = STRUMENTI[chiave]
    return [
        'Verifica in SOLA LETTURA nella factory %s, sul kanban al commit %s.' % (ctx['factory_root'], ctx['commit']),
        'Contesto: report PM «%s» del %s, voce «%s»: %s.' % (ctx['titolo'], ctx['data'], voce, descrizione),
        '',
        'Strumento factory per la VERIFICA: %s.' % s['verifica'],
        'Strumento factory per l\'eventuale MODIFICA o RICONCILIAZIONE, solo dopo la mia conferma esplicita: %s.' % s['modifica'],
        'In questa fase non modificare nessun file: proponi le correzioni e aspetta la mia conferma prima di passarle allo strumento di modifica.',
        'Prima di tutto lancia `git log --oneline %s..HEAD -- management/kanban`: se ci sono commit, il report è più vecchio del kanban. '
        'In quel caso verifica su HEAD, che è lo stato vero di oggi, e usa il commit %s solo per dire, riga per riga, cosa è già stato corretto e cosa resta.' % (ctx['commit'], ctx['commit']),
        '',
    ] + regole_lettura(ctx)


def regole_lettura(ctx):
    """Regole comuni a tutti i prompt: commit fisso, fonte degli stati, file grandi (misurati a ogni report)."""
    righe = ['Regole di lettura:',
             '- non lanciare /session-start (nemmeno l\'avvio automatico previsto dal CLAUDE.md, che scrive in memory/active-sessions.yaml), '
             'pull, fetch o sync dei submodule, che modificano file;',
             '- la fonte degli stati è il frontmatter dei file TSK/US/EP del kanban (appartenenza dai campi story/us ed epic/ep); '
             'sprint.md non è una fonte: diverge dai file;']
    fg = ctx.get('file_grandi') or {}
    elenco = fg.get('file') or []
    rilevanti = [f for f in elenco if not f['path'].startswith('deliverables/')][:8]
    if elenco:
        righe.append('- file grandi in questa factory (oltre %d righe: %d file, misurati oggi), da non leggere per intero ma con Grep o Read con offset/limit: %s;' % (
            fg['soglia'], len(elenco), ', '.join('%s (%d)' % (f['path'], f['righe']) for f in rilevanti)))
    righe.append('')
    return righe


def _coda(domande):
    righe = ['', 'Per ciascuno:']
    righe += ['%d. %s' % (i + 1, d) for i, d in enumerate(domande)]
    righe += ['',
              'Rispondi con una tabella: ID (sintesi) | stato nel kanban | cosa hai verificato | esito | fonte | proposta (nessuna / correzione).'] + STANDARD_VERIFICA
    return righe


def _etichetta(i, titoli):
    t = (titoli.get(i) or '').strip()
    return '%s (%s)' % (i, t[:90]) if t else i


def per_categoria(ctx, voce, categoria, elenco, titoli):
    """elenco: [{'id','stato'}] per le categorie di stato; [{'tsk','prerequisito','stato'?}] per i prerequisiti."""
    righe = _testa(ctx, voce, DESCRIZIONE[categoria], categoria)
    righe.append('Elenco (%d):' % len(elenco))
    for x in elenco:
        if 'prerequisito' in x:
            stato = (' — status del prerequisito: %s' % x['stato']) if x.get('stato') else ''
            righe.append('- %s → attende %s%s' % (_etichetta(x['tsk'], titoli), _etichetta(x['prerequisito'], titoli), stato))
        else:
            righe.append('- %s — status: %s' % (_etichetta(x['id'], titoli), x.get('stato')))
    return '\n'.join(righe + _coda(DOMANDE[categoria]))


def sezione_vuota(ctx, nome_sezione, us):
    righe = _testa(ctx, nome_sezione, 'la US di sezione non ha TSK registrati', 'sezione_vuota')
    righe.append('US di sezione: ' + ', '.join('%s (%s)' % (u['id'], u['titolo'][:90]) for u in us))
    righe += ['', 'Verifica:',
              '1. esistono TSK, sotto altre US, che lavorano su questa sezione? Quali (ID con sintesi e fonte)?',
              '2. serve una taskificazione della US? Se sì, proponi i TSK, senza crearli.',
              '', 'Non dedurre dai path: indica la fonte di ogni legame.'] + STANDARD_VERIFICA
    return '\n'.join(righe)


DESCR_QUALITA = {
    'superseded-by-non-valido': 'campo superseded_by non leggibile come ID o che punta a un ID inesistente',
    'chiusura-senza-metadati': 'TSK chiusi senza esito senza campi strutturati di chiusura (superseded_by, superseded_at/closed_at, superseded_reason/resolution)',
    'updated-non-aggiornato': "campo updated più vecchio dell'ultimo commit che ha modificato il file",
    'us-non-aggiornata': 'US con uno status incoerente con i propri TSK',
    'ep-non-aggiornata': 'epica con uno status incoerente con i propri TSK',
    'stato-sconosciuto': 'status non previsto dalla configurazione del report',
    'dipendenza-fuori-snapshot': 'depends_on verso un elemento fuori dal perimetro del report',
    'giorno-data-incoerente': 'giorno della settimana che non corrisponde alla data (es. «mer 06/10» con il 06/10 martedì): la data di piano è ambigua',
    'blocks-incompleto': 'blocks di un TSK che non elenca un TSK che lo ha in depends_on (legame scritto da una parte sola)',
    'depends-on-incompleto': 'depends_on di un TSK che non elenca un TSK che lo ha in blocks (legame scritto da una parte sola)',
    'esito-corpo-diverso': 'US o epica che nel testo dichiarano un TSK completato mentre il TSK è chiuso senza esito, o viceversa',
}
STRUMENTO_QUALITA = {'us-non-aggiornata': 'rollup', 'ep-non-aggiornata': 'rollup', 'dipendenza-fuori-snapshot': 'prerequisito_fuori_perimetro',
                     'esito-corpo-diverso': 'esito_corpo'}


def qualita(ctx, findings):
    codici = sorted({f['codice'] for f in findings})
    chiave = STRUMENTO_QUALITA.get(codici[0], 'qualita') if len(codici) == 1 else 'qualita'
    descr = DESCR_QUALITA.get(codici[0], 'anomalie rilevate nei file del kanban letti per il report') if len(codici) == 1 else 'anomalie rilevate nei file del kanban letti per il report'
    righe = _testa(ctx, 'Qualità del dato', descr, chiave)
    righe.append('Anomalie (%d):' % len(findings))
    righe += ['- %s · %s: %s' % (f['livello'], f['entita'], f['evidenza']) for f in findings]
    righe += ['', 'Per ciascuna: verifica l\'anomalia sul file e proponi la correzione (o spiega perché non è un errore).',
              'Rispondi con una tabella: anomalia | cosa hai verificato | esito | fonte | proposta.'] + STANDARD_VERIFICA
    return '\n'.join(righe)


def allineamento_config(ctx, n):
    return '\n'.join([
        'Allinea la configurazione del report PM (%s) al kanban al commit %s.' % (ctx.get('config') or 'config dell\'operatore', ctx['commit']),
        'Il controllo ha trovato %d elementi del kanban che la configurazione non conosce o che ha superato.' % n,
        'Segui il passo 1 «Allineamento della configurazione» della skill .claude/skills/coordinamento-giornaliero.md: proponimi le modifiche con motivo e fonte, e applicale solo dopo la mia conferma.',
        'Il prompt del subagente e le sue regole di lettura sono in .claude/skills/references/coordinamento/agente-allineamento-config.md.',
    ])
