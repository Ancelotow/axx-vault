# Validation locale — 5 novembre 2026

Machine utilisée : macOS 27.2, Apple Silicon arm64. Python 3.14, Qt 6.12,
SDK .NET 10.0.401. Cette machine ne permet pas d’exécuter les binaires Windows.

`python -m pytest -q` : **29 tests réussis**.

Tests effectués avec le vrai moteur compilé depuis les sources :

- Lecture d’un fichier AxCrypt 1 et de fichiers AxCrypt 2 AES-128 / AES-256
  issus des jeux de test historiques Xecrets Net ; vérification des empreintes.
- Aller-retour des contenus et du nom original avec accents, espaces, guillemets,
  caractères ressemblant à des options et antislashs finaux dans le mot de passe.
- Fichier aléatoire de plus de 1 Mo : absence de la restriction des builds commerciaux.
- Mauvais mot de passe et altération du contenu : aucun fichier clair exporté.
- Refus d’écraser un fichier existant, y compris un lien symbolique pendant.
- Annulation d’un vrai processus ; conservation de l’original et absence de résultat partiel.
- Nettoyage du dossier temporaire après lecture et absence du mot de passe dans les arguments processus.
- Noms internes traversant des dossiers ou utilisant des noms réservés : neutralisation.
- Interface : sélection, confirmation du mot de passe, texte HTML affiché sans exécution,
  PDF chargé depuis la mémoire, et parcours complet de chiffrement avec le vrai worker Qt.

`python tools/check_macos_package.py` vérifie la signature ad hoc du paquet,
le déchiffrement AxCrypt 1 avec le moteur inclus et le démarrage du binaire graphique.

Le paquet Windows x64 portable contient un moteur PE32+ x64 compilé, le Python
embarqué officiel et les roues Qt natives Windows. Il est **préparé, mais pas exécuté
ni validé sur Windows ici**. Le workflow CI permet la compilation et les tests natifs.
macOS Intel et les versions antérieures de macOS ne sont pas testés sur cette machine.
