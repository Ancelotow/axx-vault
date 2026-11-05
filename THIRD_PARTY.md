# Composants tiers

AxxVault est une application indépendante ; AxCrypt est une marque de son propriétaire.

- **Xecrets Cli**, copyright Svante Seleborg / Axantum Software AB, GPL-3.0-or-later : https://github.com/xecrets/xecrets-cli
- **Xecrets Net**, dérivé d’AxCrypt, copyright AxCrypt AB, Axantum Software AB et contributeurs, GPL-3.0-or-later : https://github.com/axantum/xecrets-net
- **Xecrets Slip39**, copyright Svante Seleborg, MIT : https://github.com/xecrets/xecrets-slip39
- **Qt / PySide6 / Shiboken**, The Qt Company et contributeurs : licences GPL/LGPL selon le module. Les licences fournies par la distribution se trouvent dans l’installation PySide6 et les sources officielles : https://doc.qt.io/qtforpython-6/licenses.html
- **Python**, Python Software Foundation License : https://docs.python.org/3/license.html
- **.NET**, MIT et notices tierces Microsoft : https://github.com/dotnet/runtime/blob/main/LICENSE.TXT
- **PyInstaller**, GPL avec exception pour les applications générées : https://pyinstaller.org/en/stable/license.html

Les textes de licence Python, Qt GPL/LGPL et les licences affichées par le moteur
figurent dans le dossier licenses fourni avec les paquets.
Les sources correspondantes des trois dépôts Xecrets, leurs licences et les fichiers
de projet avec les versions NuGet figurent dans l’archive AxxVault-sources.zip créée
avec chaque paquet. Le moteur est compilé depuis les sources GPL publiques, sans
les restrictions des binaires commerciaux Axantum. Les révisions exactes sont
enregistrées par tools/build_engine.py et dans le manifeste inclus avec le binaire.

La commande `XecretsCli --full-license` affiche également les licences du moteur
et de ses dépendances. AxxVault ne modifie pas les algorithmes cryptographiques du moteur.
