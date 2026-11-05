Ces trois fichiers proviennent du projet Xecrets Net, sous GPL-3.0-or-later :
https://github.com/axantum/xecrets-net/tree/1b9e6da70f4632d022107bfc69386df74f47569a/AxCrypt.Core.Test/resources

- helloworld-key-a-txt.axx : AxCrypt 1 / AES-128 ; mot de passe `a` ; contenu `HelloWorld`.
- short-txt-V2AES128.axx : AxCrypt 2 / AES-128.
- short-txt-AES256.axx : AxCrypt 2 / AES-256.

Les deux derniers utilisent le mot de passe public `PâsswördètMëd§½ Lôñg|´¨`.
Les empreintes attendues proviennent de TestV2RegressionCompleteFiles.cs dans le même dépôt.
Ils sont indépendants des fichiers produits par AxxVault durant ses tests.
