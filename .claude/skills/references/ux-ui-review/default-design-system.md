# Default fallback design system (ADR-018)

Ambito: dettaglio del default DS usato in `ux-ui-review-protocol.md` Step 2 quando
la cascata DS arriva al fallback (`source: defaults`). Leggere se `tokens_source: defaults`.

Lista minimale di **5 famiglie di token** usata quando la cascata DS (Step 2) arriva al
fallback. Conoscenza procedurale del framework, non config del derivatore (override via
`ux_ui.design_system_path`, cascata step 1). Referenziata anche da `ux-ui-design-protocol`.

```yaml
defaults:
  source: defaults                    # tag esplicito (US-031 contract)
  type:
    fontFamilies:
      - system-ui, -apple-system, "Segoe UI", Roboto, sans-serif
    sizes:                            # modular scale 1.25 (major third)
      - { name: xs, value: 12px }
      - { name: sm, value: 14px }
      - { name: md, value: 16px }     # base
      - { name: lg, value: 20px }
      - { name: xl, value: 24px }
      - { name: xxl, value: 32px }
    lineHeights:
      - { name: tight,   value: 1.2 }
      - { name: regular, value: 1.5 }
      - { name: loose,   value: 1.75 }
    weights:
      - { name: regular, value: 400 }
      - { name: medium,  value: 500 }
      - { name: bold,    value: 700 }
  colors:                             # tailwind-inspired neutral palette
    neutral:
      - { name: white,  value: "#FFFFFF" }
      - { name: 50,     value: "#F9FAFB" }
      - { name: 100,    value: "#F3F4F6" }
      - { name: 500,    value: "#6B7280" }
      - { name: 900,    value: "#111827" }
      - { name: black,  value: "#000000" }
    semantic:                         # generici, no brand
      - { name: primary,  value: "#2563EB" }   # blue-600
      - { name: success,  value: "#16A34A" }   # green-600
      - { name: warning,  value: "#CA8A04" }   # yellow-600
      - { name: danger,   value: "#DC2626" }   # red-600
  spacing:                            # scale lineare 4px (rhythm 0.25rem)
    - { name: 0,  value: 0   }
    - { name: 1,  value: 4px  }
    - { name: 2,  value: 8px  }
    - { name: 3,  value: 12px }
    - { name: 4,  value: 16px }       # base
    - { name: 6,  value: 24px }
    - { name: 8,  value: 32px }
    - { name: 12, value: 48px }
  radii:                              # 3 valori, no over-engineering
    - { name: sm,   value: 4px  }
    - { name: md,   value: 8px  }
    - { name: full, value: 9999px }
  focus:                              # 5a famiglia, critical per a11y by design
    - { name: ring_width,   value: 2px }
    - { name: ring_offset,  value: 2px }
    - { name: ring_color,   value: "#2563EB" }  # = colors.semantic.primary
    - { name: ring_style,   value: solid }
```

## Regola applicativa

Con `source: defaults` la conformance check NON emette deviations `major/minor` — solo
`open_questions` (ADR-018 §Vincoli applicativi punto 3). Se DS non disponibile, annotare
nel report la formula verbatim:

> Design system non disponibile; review basata su euristiche Nielsen e default fallback
> documentati (ADR-018). Coerenza interna non verificabile rispetto a un sistema di
> riferimento del progetto.

E aggiungere automaticamente `open_questions: ["design system non disponibile; review usa
default fallback (ADR-018)"]`.

[^src: design_&_architecture/decisions/ADR-018.md §Lista minimale]
[^src: design_&_architecture/decisions/ADR-018.md §Vincoli applicativi]
