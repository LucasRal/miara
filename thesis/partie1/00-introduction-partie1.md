# Introduction de la partie 1 {-}

Ce mémoire porte sur la conception, la réalisation et l'évaluation d'une
plateforme logicielle multi-locataire mettant des agents conversationnels
fondés sur de grands modèles de langue au service de deux fonctions
d'entreprise : la fonction commerciale, assistée dans sa relation à un
logiciel de gestion de la relation client, et la fonction ressources
humaines, assistée dans la présélection de candidatures.

La partie 1, que ce texte introduit, ne décrit pas encore le système. Elle
établit ce qu'il faut savoir pour juger les décisions qui seront prises dans
la partie 2, et elle le fait en trois temps. Le **chapitre 1** retrace la
filiation technique qui mène des réseaux récurrents aux modèles instruits
capables d'appeler des outils, et s'achève sur les limites établies de ces
modèles, dont chacune se traduira par une contrainte de conception. Le
**chapitre 2** examine ce que l'on construit avec ces modèles dans un
système d'information d'entreprise : typologies d'agents, orchestration,
stratégies de récupération de données, cas d'usage commercial et de
recrutement, méthodes d'évaluation, cadres de sécurité et de gouvernance. Le
**chapitre 3** confronte ces possibilités techniques au terrain visé, celui
des petites et moyennes entreprises malgaches, et en déduit des critères
d'acceptabilité.

Chacun de ces trois chapitres se termine par une section intitulée « Ce que
cela implique pour notre conception ». Ces sections ne sont pas des résumés :
elles relient explicitement chaque élément d'analyse à une décision
d'architecture effectivement prise et documentée dans le dépôt du projet, sous
la forme d'enregistrements de décision numérotés ADR-001 à ADR-011. Le lecteur
peut donc, dès la fin de la partie 1, vérifier qu'aucune décision de la
partie 2 n'est arbitraire.

Quatre hypothèses de travail orientent l'ensemble du mémoire et seront
confrontées à des mesures dans la partie 3 :

- **H1.** Une chaîne de traitement de présélection fondée sur un modèle de langue produit un
  classement de candidatures dont l'ordre s'accorde avec celui d'un
  annotateur humain, pour un temps de traitement très inférieur à un examen
  manuel.
- **H2.** Un agent doté d'outils de lecture typés réduit le temps nécessaire à
  la préparation d'un rendez-vous commercial par rapport à une consultation
  directe du logiciel de gestion de la relation client.
- **H3.** Une récupération contextuelle structurée, sans index vectoriel, permet
  de tenir une latence de réponse conversationnelle inférieure à trois
  secondes au 95e centile.
- **H4.** Le coût unitaire des appels au modèle, mesuré par organisation et par
  lot, reste compatible avec le budget logiciel d'une petite ou moyenne
  entreprise malgache.

Deux précautions de méthode, enfin. La première est terminologique : le
mémoire est rédigé en français, tout terme technique est défini à sa première
occurrence et repris dans le glossaire de l'annexe A, et les termes anglais ne
sont donnés qu'entre parenthèses, à titre de repère bibliographique. La seconde
est documentaire : aucune donnée chiffrée n'est avancée sans une source
vérifiée, identifiée par son titre exact, son année de publication et, pour les
données statistiques, l'année à laquelle la donnée se rapporte. Lorsqu'une
information utile n'a pas pu être vérifiée auprès d'une source primaire, le
texte le signale explicitement plutôt que d'en proposer une approximation.
