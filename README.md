# Inventaire textile de la maison

Application web du cahier des charges *Home Textile Inventory* : un inventaire familial partagé, des lieux de rangement imbriqués, des rôles, des photos, et un moteur de compatibilité (linge de lit, nappes, rideaux).

Le client est une interface web responsive (navigateur mobile, ordinateur, bureau). L’API REST et PostgreSQL tournent dans Docker. Les applications natives iOS et Android ne sont pas dans ce dépôt : elles peuvent réutiliser la même API.

## Démarrage

```bash
docker compose up --build
```

Ouvrir http://localhost:8080

Comptes de démonstration, mot de passe `Demo1234!` :

- `demo@home-textile.local` — administrateur
- `editor@home-textile.local` — édition
- `viewer@home-textile.local` — lecture seule

La documentation interactive de l’API est sur http://localhost:8080/docs

## Ce que fait l’application

- Groupes familiaux, invitations, rôles administrateur / éditeur / lecteur, contrôles côté serveur
- Maisons, pièces, rangements imbriqués, QR code d’un emplacement
- Catégories du cahier des charges, champs propres à chaque catégorie, catégories personnalisées
- Articles et unités physiques (lieu et statut séparés), historique, photos
- Recherche combinée, y compris une requête en langage courant simple
- Lits, matelas, tables et fenêtres
- Compatibilité technique par les mesures, puis score visuel séparé
- Ensembles enregistrés, export CSV, suggestions photo sans inventer de mesures

Les débords de nappe, de drap et le ratio de fronces ont des valeurs par défaut. L’interface les présente comme des suggestions tant que le foyer ne les a pas choisies.

## Sauvegarde

```bash
docker compose exec db pg_dump -U textile textile > inventory-backup.sql
```

Les photos sont dans le volume Docker `photos`.
