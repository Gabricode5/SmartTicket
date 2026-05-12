# Gestion des Rôles (Admin, User, SAV)

Dans le backend (FastAPI), la notion de rôle **Admin** (ainsi que "user" et "sav") est gérée via un **modèle relationnel** avec une clé étrangère dans la base de données PostgreSQL. 

Voici comment cela fonctionne en détail, en se basant sur les fichiers `models.py`, `schemas.py` et `main.py`.

## 1. Structure de la Base de Données (`models.py`)

La base de données utilise deux tables spécifiques pour gérer les rôles :

*   **La table `Role` (`roles`)** : Cette table contient les valeurs textuelles réelles des rôles. Elle possède une colonne `id` et une colonne `nom_role`. Le rôle "admin" existe en tant que ligne dans cette table (par exemple, `id: 3, nom_role: "admin"`).
*   **La table `Utilisateur` (`utilisateur`)** : Le modèle utilisateur ne stocke pas directement le mot "admin". À la place, il stocke un `id_role` qui est une clé étrangère (Foreign Key) liée à la table `roles`.

```python
# models.py
class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    nom_role = Column(String(20), unique=True, nullable=False) # ex: "admin", "user", "sav"

class Utilisateur(Base):
    __tablename__ = "utilisateur"
    # ...
    id_role = Column(Integer, ForeignKey("roles.id"), server_default="1")
    role = relationship("Role") # Fait le lien entre les deux tables
```

## 2. Validation du rôle Admin (`main.py`)

Pour vérifier si un utilisateur est un administrateur (ou fait partie du SAV), l'application utilise la relation SQLAlchemy (`user.role`) pour suivre la clé étrangère et lire le `nom_role` à partir de la table `roles` de manière dynamique.

```python
# main.py
def is_admin_or_sav(user: models.Utilisateur | None):
    if not user or not user.role:
        return False
    # Vérifie si la chaîne de caractères correspond à la ligne de la table liée
    return user.role.nom_role in ["admin", "sav"]
```

## 3. Comment attribuer ou stocker le rôle Admin

Si un Administrateur existant souhaite promouvoir un autre utilisateur au rang d'Admin, il envoie une requête `PUT /users/{user_id}` ou `PUT /users/{user_id}/role`. Voici ce qui se passe dans le backend (`main.py`) :

1.  **Autorisation** : Le système vérifie d'abord que le demandeur est bien un administrateur en vérifiant la condition `requester.role.nom_role == "admin"`.
2.  **Recherche** : Il recherche dans la table `roles` l'enregistrement spécifique correspondant à `"admin"`.
3.  **Attribution** : Il récupère l'`id` de cet enregistrement de rôle et met à jour la colonne `target_user.id_role` de l'utilisateur ciblé.

```python
# main.py (À l'intérieur des fonctions update_user_role ou update_user_by_admin)

# 1. Trouve la ligne correspondante dans la table `roles` qui correspond à "admin"
role_row = db.query(models.Role).filter(models.Role.nom_role == "admin").first()

# 2. Attribue l'ID de ce rôle à la colonne id_role de l'utilisateur cible
target_user.id_role = role_row.id
db.commit()
```

## 4. Pré-requis (Résumé)

Pour s'assurer que le rôle administrateur puisse être stocké et utilisé correctement :

1.  **Initialisation de la base de données (Seeding)** : La table `roles` de votre base de données PostgreSQL **doit** être initialement peuplée avec des lignes où `nom_role` est égal à `"user"`, `"sav"`, et `"admin"`. *(Si ces rôles n'existent pas dans la table `roles`, vous ne pourrez affecter ces rôles à aucun compte).*
2.  **Affectation** : Assigner un rôle administrateur signifie simplement mettre à jour l'`id_role` d'un utilisateur dans la table `utilisateur` pour qu'il corresponde à l'ID de la ligne `"admin"` dans la table `roles`.
