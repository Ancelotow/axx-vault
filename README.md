# AxxVault

Application de bureau en français pour **lire, déchiffrer et chiffrer des fichiers AxCrypt**,
sans compte et hors ligne. Interface Qt / PySide6 ; moteur Xecrets Cli compilé depuis ses
sources GPL, issues d’AxCrypt. Windows 11 x64 et macOS 14 ou ultérieur, Apple Silicon / Intel.

## Utilisation

1. Lancez AxxVault et ajoutez des fichiers, ou glissez-les dans la fenêtre.
2. Sélectionnez un fichier et cliquez sur **Lire le fichier** pour consulter un PDF, une image
   ou un texte UTF-8 / UTF-16 en lecture seule.
3. Utilisez **Déchiffrer…** pour exporter les originaux dans le dossier de votre choix.
4. Utilisez **Chiffrer…** pour créer des fichiers `.axx` avec un nouveau mot de passe confirmé
   d’au moins 12 caractères. Plusieurs fichiers peuvent être traités ensemble avec le même mot de passe.

Les fichiers d’origine sont conservés. Un résultat existant n’est jamais écrasé : choisissez un
autre dossier ou déplacez le fichier existant. L’état de chaque fichier apparaît dans le tableau ;
survolez « Échec » pour connaître la cause. Annuler arrête le fichier en cours ; les résultats
déjà terminés restent disponibles. Le double-clic lance la lecture du fichier sélectionné.

## Compatibilité

| Opération | Format |
| --- | --- |
| Lecture / déchiffrement | AxCrypt 1 AES-128 ; AxCrypt 2 AES-128 / AES-256, accessibles par mot de passe |
| Chiffrement | AxCrypt 2 AES-256 ; lisible par AxCrypt 2 et Xecrets |
| Aperçu | PDF, PNG, JPEG, BMP, GIF, WebP, TIFF, texte UTF-8 / UTF-16 |

Les fichiers créés ne sont pas lisibles par AxCrypt 1. L’accès par clé privée partagée,
les anciens fichiers-clés AxCrypt 1, les exécutables auto-décryptants, la récupération
de compte et le contournement d’un mot de passe perdu ne sont pas proposés.
Un fichier partagé uniquement avec une clé publique nécessite la clé privée correspondante.
L’aperçu est limité à 32 Mo, le texte à 4 Mo et les images à 40 millions de pixels.
Les fichiers plus grands peuvent être déchiffrés sur disque. Les fichiers Office et autres
formats binaires s’utilisent après export, avec leur application habituelle.

## Lancer depuis les sources

Prérequis de développement : Python 3.12 ou ultérieur, Git et SDK .NET **10.0.401**.
Python et .NET ne sont pas nécessaires pour utiliser les applications empaquetées.
La première installation télécharge les dépendances ; l’utilisation est ensuite hors ligne.

macOS :

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python tools/build_engine.py
python -m axxvault
```

Windows, PowerShell :

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe tools\build_engine.py
.venv\Scripts\python.exe -m axxvault
```

Le moteur est compilé localement à partir de trois révisions précises. Il ne nécessite pas
d’abonnement Xecrets et n’impose pas de limite de taille commerciale.
Ne réutilisez pas des binaires commerciaux téléchargés pour remplacer ce moteur.

## Créer les applications

Sur chaque système cible, après l’installation ci-dessus :

```sh
python -m pytest -q
python tools/package_app.py
```

Le résultat se trouve dans `dist` : application macOS `.app` et archive ZIP, ou dossier
Windows avec `AxxVault.exe` et archive ZIP. Sous Windows, conserver tout le dossier extrait.
Les sources correspondantes sont regroupées dans `AxxVault-sources.zip`.
Un paquet Windows portable peut aussi être **assemblé depuis macOS** avec
`python tools/package_windows_portable.py` : il embarque Python, Qt et le moteur
Windows x64. Extraire tout le ZIP, puis lancer `AxxVault.cmd`. Cet assemblage
ne remplace pas un test d’exécution sur Windows.
La compilation native est requise pour l’interface : le paquet macOS ne peut pas être
transformé directement en exécutable Windows. Le workflow GitHub Actions fourni compile
et teste séparément Windows x64, macOS Apple Silicon et macOS Intel ; il ne publie rien.
Les artefacts sont non signés par un certificat de distribution ; la signature macOS locale
est ad hoc. Signature Developer ID, notarisation et signature Windows restent à configurer
pour une distribution publique.

## Protection des données

- Le chiffrement et la vérification d’intégrité sont confiés au moteur Xecrets, sans algorithme maison.
- Les mots de passe sont transmis au processus par son environnement privé et ne figurent pas dans
  sa ligne de commande. Aucun mot de passe, historique ou fichier récent n’est enregistré par l’interface.
  Un processus privilégié peut toujours lire la mémoire ou l’environnement d’un autre processus.
- Les données sont traitées dans un dossier temporaire privé, nettoyé à la fin normale ou à l’annulation.
  Un résultat n’est exporté qu’après validation complète par le moteur ; les fichiers partiels créés
  pendant une copie annulée sont supprimés. Le nom interne est traité comme une donnée non fiable.
- L’aperçu charge le document en mémoire après vérification, puis supprime sa copie temporaire sur disque.
  Il n’ouvre pas automatiquement d’application externe, ne rend pas de HTML actif et n’exécute pas de fichier.
- La suppression n’est pas un effacement physique garanti sur SSD. Un arrêt brutal peut laisser un dossier
  temporaire `axxvault-*` ; la mémoire Python et les caches système ne peuvent pas être effacés de façon garantie.

Ces limites sont celles de cette application, qui n’a pas fait l’objet d’un audit de sécurité indépendant.
Les tests comprennent de vrais fichiers historiques AxCrypt 1 et 2, et ne se limitent pas aux aller-retours
de chiffrement produits par l’application.

## Licence

GPL-3.0-or-later. Voir LICENSE et THIRD_PARTY.md. Les noms AxCrypt et Xecrets servent
à identifier la compatibilité et les composants ; AxxVault n’est pas affilié à AxCrypt AB.
