# Mémoire — sources et compilation

Le mémoire est écrit en Markdown, une partie par dossier, un fichier par
chapitre. La bibliographie unique est `thesis/refs.bib`. Pandoc assemble le
tout en PDF.

```
thesis/
├── refs.bib              bibliographie BibTeX (toutes parties)
├── build.sh              compilation d'une partie
├── build/                sorties PDF (ignoré par git)
├── pandoc/
│   ├── metadata.yaml     métadonnées et mise en page communes
│   ├── entete.tex        réglages LaTeX (en-têtes, espacements)
│   └── iso690-author-date-fr.csl   style de citation (ISO 690, français)
├── partie1/ … partie3/
│   ├── partie.yaml       sous-titre de la partie
│   └── 00-*.md …         chapitres, compilés dans l'ordre lexicographique
└── soutenance/
    ├── diapositives.md   support de soutenance (Beamer, `make slides`)
    ├── build-slides.sh   compilation des diapositives
    ├── demo.md           déroulé reproductible de la démonstration
    └── demo/             artefacts de la démonstration (captures, journaux)
```

## Compiler

```bash
make thesis                  # partie 1 -> thesis/build/partie1.pdf
make thesis PARTIE=partie2   # partie 2
make thesis PARTIE=partie3   # partie 3 (chapitres numérotés 7 à 9)
make slides                  # diapositives -> thesis/build/diapositives.pdf
```

Prérequis (Ubuntu) :

```bash
sudo apt-get install pandoc texlive-xetex texlive-lang-french \
                     texlive-latex-recommended texlive-fonts-recommended lmodern
```

Le moteur PDF par défaut est XeLaTeX (nécessaire pour les polices système et
les caractères accentués). Pour en changer : `THESIS_PDF_ENGINE=lualatex make thesis`.

## Remplacer la mise en page par le gabarit de l'université

**La mise en page actuelle est provisoire et volontairement sobre** : A4, 11 pt,
interligne 1,3, marges 3/2,5 cm, numérotation des sections, en-tête courant.
Elle n'est pas le gabarit officiel de l'université, qui n'est pas versionné
dans ce dépôt. Trois points d'entrée, du plus léger au plus lourd :

1. **Réglages simples** (marges, police, interligne, page de titre) :
   éditer `thesis/pandoc/metadata.yaml`. C'est suffisant si le gabarit se
   résume à des consignes de mise en forme.
2. **Commandes LaTeX supplémentaires** (en-têtes imposés, page de garde avec
   logo, styles de titres) : éditer `thesis/pandoc/entete.tex`, injecté dans le
   préambule. Placer le logo dans `thesis/` et l'appeler par un chemin relatif
   (`--resource-path` couvre déjà `thesis/`).
3. **Gabarit LaTeX complet fourni par l'université** : déposer le `.tex` dans
   `thesis/pandoc/gabarit.tex`, le transformer en gabarit Pandoc (remplacer le
   corps par `$body$`, le titre par `$title$`, la table des matières par
   `$if(toc)$\tableofcontents$endif$` — voir `pandoc -D latex` pour le gabarit
   de référence), puis ajouter `--template="$ICI/pandoc/gabarit.tex"` à l'appel
   pandoc de `thesis/build.sh`. Les variables non standard du gabarit se
   renseignent dans `metadata.yaml` et sont accessibles par `$nom$`.

Si l'université impose un format Word, remplacer `-o build/$partie.pdf` par
`-o build/$partie.docx --reference-doc=thesis/pandoc/gabarit.docx` : Pandoc
reprend alors les styles du document de référence.

## Style de citation

`iso690-author-date-fr.csl` (téléchargé depuis le dépôt Citation Style
Language, versionné ici pour que la compilation soit reproductible hors
ligne). Pour changer de style, remplacer ce fichier et l'option `--csl` dans
`build.sh`.

## Règles de rédaction

- Français formel, pas d'anglicisme ; tout terme technique est défini à sa
  première occurrence et repris dans le glossaire (annexe A).
- Aucune donnée chiffrée sans source vérifiée. Une donnée non vérifiée
  s'écrit `[À SOURCER : ...]` dans le texte et ne franchit pas la relecture.
- Chaque chapitre se termine par « Ce que cela implique pour notre
  conception », qui renvoie à l'architecture réellement livrée (`docs/adr/`,
  cartes [RÉF] du tableau Trello).
