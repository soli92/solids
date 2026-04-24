# [1.6.0](https://github.com/soli92/solids/compare/v1.5.0...v1.6.0) (2026-04-24)


### Features

* **themes:** sei palette ispirate a Ichigo, Vegeta, Zoro, Captain America, Sasuke, Inuyasha ([b1d2bf2](https://github.com/soli92/solids/commit/b1d2bf2a3ccc1ab82071aeb3cd7d6a816bd3b9e1))

# [1.5.0](https://github.com/soli92/solids/compare/v1.4.0...v1.5.0) (2026-04-08)


### Features

* steampunk theme, MD3 tokens, Storybook refresh v1.4.0 ([6005609](https://github.com/soli92/solids/commit/60056096e294bf7a75c74429da3ba015eba12b80))

# [1.4.0](https://github.com/soli92/solids/compare/v1.3.3...v1.4.0) (2026-03-26)


### Features

* **themes:** add 90s-party palette, fonts, Storybook toolbar ([bc26648](https://github.com/soli92/solids/commit/bc266489adfee951fde1a01990359cf82bd7b5e7))

## [Unreleased]

### Features

* **themes:** sei nuovi temi nominati (`captain-america`, `ichigo`, `inuyasha`, `sasuke`, `vegeta`, `zoro`) ispirati alle palette di Captain America, Ichigo (Bleach), Vegeta (Dragon Ball), Zoro (One Piece), Sasuke (Naruto), Inuyasha — JSON in `src/tokens/themes/`, `color-scheme: dark`, preset Tailwind `dark:` come gli altri temi scuri, toolbar Storybook e Google Fonts (Oswald, Rajdhani, Merriweather, Crimson Text, Bebas Neue) in `preview-head.html`.

### Documentation

* **storybook:** ordinamento sidebar (home → guide → Foundations → UI), TOC nelle pagine docs, brand **SoliDS** nel manager.
* **docs:** allineamento a sei temi (steampunk), MD3/motion, spacing con anteprime 90s-party/steampunk, radius/typography/tokens/principles/roadmap/getting-started; **shadcn-integration**: tabella colori light/dark aggiornata ed esempio **next-themes** con `themes` estesi.

## [1.4.0](https://github.com/soli92/solids/compare/v1.3.3...v1.4.0) (2026-04-08)

### Features

* **themes:** nuovo tema **`steampunk`** (`data-theme="steampunk"`) — palette ottone/rame/cuoio, accenti vapore/teal, font Cinzel / Libre Baskerville / Courier Prime (Storybook); preset Tailwind `dark:` e `color-scheme: dark` allineati a cyberpunk/90s-party.
* **tokens:** default light/dark più vicini a **Material Design 3** (superfici tonali, raggi 8/12/16/20px, ombre a doppio livello, curve di motion `standard` / `emphasized-*` in `base.json`, focus visibile con easing).
* **tailwind-preset:** `fontFamily.heading` / `serif` da `--sd-font-heading`; utility `sd-font-heading`.
* **themes:** tema **`90s-party`** (`data-theme="90s-party"`) — palette magenta/teal/lime su viola, font Russo One / Tahoma / VT323, ombre offset + glow; preset Tailwind `dark:` e Storybook toolbar + Google Fonts in preview.
* **storybook:** toolbar e **manager** allineati ai temi scuri (`90s-party`, `steampunk`); pagine **Colors** / **index** con steampunk; script **`npm test`** (build + `build-storybook`).

## [1.3.3](https://github.com/soli92/solids/compare/v1.3.2...v1.3.3) (2026-03-24)


### Bug Fixes

* **build:** sanitize CSS custom property segments for Turbopack ([f22c134](https://github.com/soli92/solids/commit/f22c134f85ba76fd19ca7ea83396252556f7365b))


### Reverts

* erroneous 1.1.0 release (wrong semver baseline) ([9842ef6](https://github.com/soli92/solids/commit/9842ef623b73feac9adb81d2e98afe60860ddab8))

## [1.3.2](https://github.com/soli92/solids/compare/v1.3.1...v1.3.2) (2026-03-24)


### Bug Fixes

* **ui:** align Resizable with react-resizable-panels v4 ([73f8bb5](https://github.com/soli92/solids/commit/73f8bb5e6210a14bcd4310042f7533907a45c848))

## [1.3.1](https://github.com/soli92/solids/compare/v1.3.0...v1.3.1) (2026-03-24)


### Bug Fixes

* **storybook:** dedupe React in Vite to avoid production error [#130](https://github.com/soli92/solids/issues/130) ([888a5b4](https://github.com/soli92/solids/commit/888a5b46b6df9ea4cdc8a8eb76daad1dc0d7048a))

# [1.3.0](https://github.com/soli92/solids/compare/v1.2.1...v1.3.0) (2026-03-24)


### Features

* fantasy/cyberpunk themes, icon set, Storybook Pages fixes ([3997055](https://github.com/soli92/solids/commit/3997055fc1f1ba0942857347c248fa61716ba665))

## [1.2.1](https://github.com/soli92/solids/compare/v1.2.0...v1.2.1) (2026-03-24)


### Bug Fixes

* **ci:** disable GitHub issue labels for semantic-release failures ([4f9f18d](https://github.com/soli92/solids/commit/4f9f18dd81793d80267a8ca7951397532850911e))

# [1.2.0](https://github.com/soli92/solids/compare/v1.1.1...v1.2.0) (2026-03-24)


### Features

* full shadcn/ui kit, Storybook UI stories, registry solids-ui block ([2d55ae5](https://github.com/soli92/solids/commit/2d55ae5310e1106570753a234096a63ee202ecd0))

## [1.1.1](https://github.com/soli92/solids/compare/v1.1.0...v1.1.1) (2026-03-24)


### Bug Fixes

* align GitHub URLs to soli92; deploy Storybook on GitHub Release ([0faeb60](https://github.com/soli92/solids/commit/0faeb60fcfdb0b3e050e3e6e1d4e239e2ec58f0d))

# [1.1.0](https://github.com/Soli92/solids/compare/v1.0.0...v1.1.0) (2026-03-24)


### Features

* tailwind preset, shadcn registry [@solids](https://github.com/solids), Storybook button showcase ([2df67ce](https://github.com/Soli92/solids/commit/2df67ce8e1b810348775a717a0a106eac614378f))

# 1.0.0 (2026-03-24)


### Bug Fixes

* **base:** add prefers-color-scheme dark support for color-scheme property ([f055741](https://github.com/soli92/solids/commit/f0557414b2fe1da5de8e46b7708676cc054f697f))
* **ci:** pass NODE_AUTH_TOKEN for npm auth via setup-node ([9de7228](https://github.com/soli92/solids/commit/9de72289c35ba69e37e5a7eecf2dd426af63d99f))
* **ci:** upgrade Node to 22 for semantic-release compatibility ([3b0f4c0](https://github.com/soli92/solids/commit/3b0f4c04e98dfb0ab4f6e3b97445d91c6a27f083))
* **docs:** fix npm package name casing (must be lowercase) + fix import paths ([e51bd71](https://github.com/soli92/solids/commit/e51bd713618c91e0893529d2570d89663c535ed2))
* **release:** add missing semantic-release core plugins to devDependencies ([8b57869](https://github.com/soli92/solids/commit/8b57869fdd2e85a3af79cb51c5bcb435b3ad313a))
* **release:** correct semantic-release plugin order (git must be last) ([94d674b](https://github.com/soli92/solids/commit/94d674b877120fd4c25bc5a42bf771912fe49341))
* **shadcn:** complete truncated dark theme block ([f7e36d9](https://github.com/soli92/solids/commit/f7e36d99cb19c9278240830f476f8652ebcfd850))
* **tokens:** add missing overlay color in dark theme ([ba011dd](https://github.com/soli92/solids/commit/ba011ddf5d43c5e77643906a79eda069683586e7))


### Features

* add real utility classes to utilities.css ([34112a4](https://github.com/soli92/solids/commit/34112a40516f9b1c964af45cbd93aca9e30634a9))
* add shadcn.css export and update package exports ([274256f](https://github.com/soli92/solids/commit/274256fe21fded1053201d2ad8a6cfe3a50eb47e))
* **css:** add shadcn/ui compatibility layer — maps shadcn vars to SoliDS tokens ([324131b](https://github.com/soli92/solids/commit/324131b18823edcc71900d840cc3a099159eb129))
* **tokens:** complete dark theme — all semantic overrides for dark mode ([8649ce5](https://github.com/soli92/solids/commit/8649ce542afa682926d73306d31d732c4985bdca))
* **tokens:** complete light theme — all semantic overrides ([6d5f857](https://github.com/soli92/solids/commit/6d5f857581a8642da6eab5dcd30c1eb1987d8c4d))
* **tokens:** complete semantic tokens — text, bg, border, intent, interactive ([668d4b0](https://github.com/soli92/solids/commit/668d4b0b21bf98b624aa33f4a7709937a537d5d6))
* **tokens:** expand base palette — full color scale, typography, shadow, spacing ([06f1499](https://github.com/soli92/solids/commit/06f1499ccfc003d39c082590048d1484ef24f6af))
* update build script to generate shadcn.css and full CSS variables ([a483dae](https://github.com/soli92/solids/commit/a483dae64fc1ca97013dfd16124a73ad8609a2cd))
