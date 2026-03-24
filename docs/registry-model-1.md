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

5. **Registry SoliDS** — aggiungi il namespace nel `components.json` del **tuo** progetto (sostituisci `soli92/solids` e `main` se usi fork o branch diverso):

   ```json
   {
     "registries": {
       "@solids": {
         "url": "https://raw.githubusercontent.com/soli92/solids/main/registry/r/{name}.json"
       }
     }
   }
   ```

6. **Installa i blocchi SoliDS**

   **Kit completo** (tutti i componenti shadcn/ui allineati a SoliDS, come in Storybook):

   ```bash
   npx shadcn@latest add @solids/solids-ui
   ```

   Installa anche `@solids/solids-utils` e le dipendenze npm elencate nel payload del registry.

   **Solo il Button** (progetti minimali):

   ```bash
   npx shadcn@latest add @solids/solids-button
   ```

   **Icone SVG** (token `--sd-color-icon-*`):

   ```bash
   npx shadcn@latest add @solids/solids-icons
   ```

7. **Componenti extra da shadcn** — per blocchi non ancora nel registry (es. *combobox* se assente), usa `npx shadcn@latest add @shadcn/…` dopo aver allineato CSS e preset SoliDS.

---

## Sviluppo nel repo SoliDS (mantenitori)

- **Sorgente canonica** dei componenti esposti: `src/lib/utils.ts`, `src/icons/*` e `src/components/ui/*` (usati anche da Storybook).
- **Sync + build JSON** per GitHub Raw:

  ```bash
  npm run registry:build
  ```

  Lo script copia i file in `registry/solids/` e genera `registry/r/*.json`.

- Dopo ogni modifica ai componenti in `src/components/ui` o agli hook, esegui `npm run ui:stories` (o `npm run storybook` / `build-storybook`), poi `npm run registry:build`, e committa `registry/solids/**`, `registry/r/**` e `registry.json`.

- Nuove dipendenze npm introdotte da `shadcn add`: aggiorna anche `scripts/solids-ui-npm-deps.json` così il blocco `@solids/solids-ui` installa i pacchetti corretti nei progetti consumer.

---

## Alternative senza namespace

Puoi installare da URL diretto (utile per prove rapide):

```bash
npx shadcn@latest add https://raw.githubusercontent.com/soli92/solids/main/registry/r/solids-utils.json
npx shadcn@latest add https://raw.githubusercontent.com/soli92/solids/main/registry/r/solids-button.json
```

In questo caso `solids-button` potrebbe non risolvere automaticamente `solids-utils` se la CLI si aspetta il namespace; preferisci il flusso con `@solids` nel `components.json`.

---

## Storybook su GitHub Pages

A ogni **GitHub Release** (creata da semantic-release insieme al publish npm) il workflow **Deploy Storybook** genera lo static e lo pubblica su `https://soli92.github.io/solids/`. La prima volta: *Repository → Settings → Pages → Build and deployment → Source: GitHub Actions*.

---

## Riferimenti

- Schema registry: [registry.json](https://ui.shadcn.com/docs/registry/registry-json) · [registry item](https://ui.shadcn.com/docs/registry/registry-item-json)
- Namespace: [shadcn registry namespace](https://ui.shadcn.com/docs/registry/namespace)
- CLI `build`: [shadcn CLI](https://ui.shadcn.com/docs/cli)
