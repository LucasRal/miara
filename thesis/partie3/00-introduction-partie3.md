```{=latex}
% Les chapitres de cette partie sont les chapitres 7, 8 et 9 du mémoire.
% Pandoc repart de 1 à chaque compilation de partie : on décale le compteur.
\setcounter{chapter}{6}
% Les noms de fichiers cités sous les tableaux sont longs et non sécables :
% on autorise un espacement inter-mots plus lâche plutôt que des débordements.
\sloppy
```

# Introduction de la partie 3 {-}

La partie 1 a établi ce qu'il est possible de construire avec un modèle de
langue et ce que le terrain malgache impose à un logiciel qui prétend y être
vendu. La partie 2 a décrit le système effectivement construit, décision par
décision. Cette troisième partie fait le travail qui donne son sens aux deux
précédentes : elle confronte le système à des mesures, et elle rend un verdict
sur les quatre hypothèses posées en introduction de la partie 1.

Ce verdict n'est pas favorable partout. Sur les treize seuils de service que le
projet s'était fixés avant de mesurer, cinq ne sont pas tenus, et l'un des
quatre énoncés d'hypothèse, celui qui porte sur la latence conversationnelle,
est explicitement infirmé au 95\textsuperscript{e} centile. Deux autres ne sont
pas tant infirmés que **non démontrés** : le dispositif expérimental construit
pour ce mémoire ne comporte pas la mesure humaine de comparaison qu'ils
appellent, et aucune reformulation du protocole ne peut faire dire à des
chiffres ce qu'ils ne disent pas. Ces résultats sont présentés comme des
résultats, au même rang que ceux qui confirment, parce qu'un dispositif
d'évaluation qui ne produirait jamais de mauvaise nouvelle ne mesurerait rien.

La partie s'organise en trois temps. Le **chapitre 7** expose la méthodologie :
la stratégie retenue pour évaluer un produit d'entreprise sans accès à une
entreprise réelle, la construction et l'annotation du jeu de données de
référence, la définition de chaque métrique et la justification écrite de
chaque seuil, le protocole d'exécution du harnais et de la campagne de charge,
et enfin les menaces à la validité, dont deux qui se sont matérialisées en
cours de route. Le **chapitre 8** présente les résultats mesurés. Il obéit à une
règle unique et stricte : aucun chiffre n'y figure qui ne provienne d'un fichier
archivé dans le dépôt, et chaque tableau cite sa source par son nom de fichier
sous le tableau. Lorsqu'une mesure annoncée n'a pas pu être produite ou n'a pas
été archivée, le chapitre le dit à la place du chiffre. Le **chapitre 9**
discute ces résultats : verdict explicite pour chacune des quatre hypothèses,
telles qu'elles ont été formulées et sans reformulation de circonstance ;
limites du dispositif ; portée pour le terrain malgache ; évolutions
identifiées ; contributions revendiquées.

Une remarque de forme, enfin. Les nombres de cette partie sont donnés avec la
précision du fichier dont ils sortent, et non arrondis pour la commodité de la
lecture, parce qu'un arrondi silencieux est la première marche d'une chaîne qui
mène à des chiffres que plus personne ne peut retrouver. Le lecteur qui
souhaite vérifier une valeur trouvera le fichier source cité sous le tableau qui
la contient, et ce fichier est dans le dépôt.
