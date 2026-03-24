# Modello 1 — shadcn in repo + registry SoliDS

In questo modello i componenti UI **stanno nel progetto applicativo** (cartelle `components/`, `lib/`, …). SoliDS fornisce **token + CSS + preset Tailwind**; il registry in questo repository fornisce **snippet ufficiali** allineati a SoliDS, installabili con la CLI shadcn.

---

## Flusso in un progetto nuovo

1. **Dipendenze fondazione**

   ```bash
   npm install @soli92/solids tailwindcss tailwindcss-animate
   ```

2. **CSS globale** — in `globals.css` (o equivalente): prima SoliDS, poi Tailwind.

   ```css
   @import "@soli92/solids/css/index.css";
   @tailwind base;
   @tailwind components;
   @tailwind utilities;
   ```

3. **Tailwind** — usa il preset SoliDS (vedi [README](../README.md) o [shadcn-integration](./shadcn-integration.md)).

4. **shadcn init** nel progetto

   ```bash
   npx shadcn@latest init
   ```

   Usa `components.json` coerente con i path della tua app (esempio in [templates/components.json.example](../templates/components.json.example)).

5. **Registry SoliDS** — aggiungi il namespace nel `components.json` del **tuo** progetto (sostituisci `Soli92/solids` e `main` se usi fork o branch diverso):

   ```json
   {
     "registries": {
       "@solids": {
         "url": "https://raw.githubusercontent.com/Soli92/solids/main/registry/r/{name}.json"
       }
     }
   }
   ```

6. **Installa i blocchi SoliDS**

   ```bash
   npx shadcn@latest add @solids/solids-button
   ```

   La CLI installerà anche `@solids/solids-utils` (dipendenza dichiarata nel registry).

7. **Resto dell’UI** — per card, dialog, ecc. puoi usare **@shadcn** standard oppure aggiungere voci al registry SoliDS seguendo la stessa convenzione.

---

## Sviluppo nel repo SoliDS (mantenitori)

- **Sorgente canonica** dei componenti esposti: `src/lib/utils.ts` e `src/components/ui/*` (usati anche da Storybook).
- **Sync + build JSON** per GitHub Raw:

  ```bash
  npm run registry:build
  ```

  Lo script copia i file in `registry/solids/` e genera `registry/r/*.json`.

- Dopo ogni modifica a `utils` o `button`, esegui `registry:build` e committa **sia** `registry/solids/**` **sia** `registry/r/**` così gli URL raw restano aggiornati.

- Estendere il registry: aggiungi file sotto `registry/solids/…`, descrivi l’item in `registry.json`, usa `registryDependencies` con prefisso `@solids/…` per dipendenze interne.

---

## Alternative senza namespace

Puoi installare da URL diretto (utile per prove rapide):

```bash
npx shadcn@latest add https://raw.githubusercontent.com/Soli92/solids/main/registry/r/solids-utils.json
npx shadcn@latest add https://raw.githubusercontent.com/Soli92/solids/main/registry/r/solids-button.json
```

In questo caso `solids-button` potrebbe non risolvere automaticamente `solids-utils` se la CLI si aspetta il namespace; preferisci il flusso con `@solids` nel `components.json`.

---

## Riferimenti

- Schema registry: [registry.json](https://ui.shadcn.com/docs/registry/registry-json) · [registry item](https://ui.shadcn.com/docs/registry/registry-item-json)
- Namespace: [shadcn registry namespace](https://ui.shadcn.com/docs/registry/namespace)
- CLI `build`: [shadcn CLI](https://ui.shadcn.com/docs/cli)
