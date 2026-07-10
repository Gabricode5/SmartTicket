# Accord de sous-traitance (DPA) — SmartTicket

> **Statut : brouillon.** Ce document reprend la structure des clauses contractuelles types
> publiées par la CNIL pour l'article 28 du RGPD, adaptée au fonctionnement réel de
> SmartTicket. Ce n'est **pas** un document validé juridiquement — les champs
> `[À COMPLÉTER]` doivent être remplis (identité légale de l'entité, une fois enregistrée)
> et une relecture par un avocat spécialisé RGPD/SaaS est recommandée avant signature avec
> un premier client réel. Ce document est annexé au contrat commercial (CGV) conclu avec
> chaque client — ce n'est pas une page publique du site.

**Entre :**

- **[RAISON SOCIALE DU CLIENT]**, ci-après le « Responsable de traitement » ou « le
  Client », dont les données sont précisées dans le bon de commande ou les conditions
  particulières signées ;

**Et :**

- **[RAISON SOCIALE À COMPLÉTER]**, [FORME JURIDIQUE À COMPLÉTER], dont le siège social
  est situé [ADRESSE À COMPLÉTER], ci-après le « Sous-traitant » ou « SmartTicket » ;

Ci-après conjointement désignées « les Parties ».

## Préambule

Le Client utilise le service SmartTicket, une plateforme de support client assistée par
intelligence artificielle, dans le cadre de laquelle SmartTicket traite, pour le compte du
Client et selon ses instructions, des données à caractère personnel relatives aux
utilisateurs finaux du Client et, le cas échéant, aux membres de son équipe support. Le
présent accord a pour objet de définir les conditions dans lesquelles SmartTicket s'engage
à effectuer ce traitement, conformément à l'article 28 du Règlement (UE) 2016/679 (RGPD).

## 1. Objet et description du traitement

| | |
|---|---|
| **Objet** | Fourniture d'un service de support client assisté par IA (chat, transfert vers agents humains, base de connaissances) |
| **Nature des opérations** | Collecte, hébergement, structuration, consultation, génération de réponses assistée par IA, suppression |
| **Finalité** | Exécution du service de support client souscrit par le Client |
| **Catégories de personnes concernées** | Utilisateurs finaux du Client (ses clients, y compris en tant que visiteurs anonymes du chat) ; le cas échéant, les membres de l'équipe support du Client (comptes `sav`/`superviseur`/`admin`) |
| **Catégories de données traitées** | Email, nom d'utilisateur, prénom, nom, mot de passe (haché), contenu des messages échangés dans le cadre du support |
| **Durée du traitement** | Durée du contrat commercial, puis 30 jours suivant sa résiliation ou une demande de suppression (délai de purge RGPD) |

## 2. Obligations de SmartTicket (sous-traitant)

Conformément à l'article 28.3 du RGPD, SmartTicket s'engage à :

1. Traiter les données uniquement sur instruction documentée du Client, y compris en ce qui
   concerne les transferts vers un pays tiers, sauf obligation légale contraire (auquel cas
   SmartTicket informe le Client de cette obligation, sauf interdiction légale) ;
2. Garantir que les personnes autorisées à traiter les données se sont engagées à respecter
   la confidentialité ou sont soumises à une obligation légale de confidentialité ;
3. Mettre en œuvre les mesures de sécurité prévues à l'article 32 du RGPD, notamment :
   hachage des mots de passe (bcrypt), authentification par jeton signé (JWT) avec cookie
   `httpOnly`, contrôle d'accès par rôle sur chaque point d'accès de l'application,
   suppression en cascade des données liées à un compte supprimé, hébergement au sein de
   l'Union européenne (Render, région Frankfurt) ;
4. Respecter les conditions visées aux paragraphes 2 et 4 de l'article 28 pour recourir à un
   autre sous-traitant (cf. section 3) ;
5. Compte tenu de la nature du traitement, aider le Client, par des mesures techniques et
   organisationnelles appropriées, à s'acquitter de son obligation de donner suite aux
   demandes d'exercice des droits des personnes concernées (le Client dispose déjà, via
   l'interface SmartTicket, de fonctionnalités d'accès, de rectification, de portabilité et
   d'effacement — cf. section 5) ;
6. Aider le Client à garantir le respect des obligations prévues aux articles 32 à 36 du
   RGPD (sécurité, notification de violation, analyse d'impact), compte tenu de la nature du
   traitement et des informations à disposition de SmartTicket ;
7. Selon le choix du Client, supprimer ou renvoyer toutes les données à caractère personnel
   au terme du contrat, et détruire les copies existantes, sauf obligation légale contraire ;
8. Mettre à la disposition du Client les informations nécessaires pour démontrer le respect
   des obligations prévues au présent article et permettre la réalisation d'audits, y
   compris des inspections, menés par le Client ou un auditeur qu'il mandate.

## 3. Sous-traitants ultérieurs

Le Client autorise de manière générale SmartTicket à recourir aux sous-traitants ultérieurs
suivants, nécessaires au fonctionnement du service :

| Sous-traitant | Rôle | Localisation |
|---|---|---|
| Mistral AI | Génération des réponses de l'assistant IA à partir du contenu des messages | Union européenne |
| Render | Hébergement de l'application et de la base de données | Union européenne (Frankfurt) |
| Brevo | Envoi des emails transactionnels (vérification de compte, notifications) | Union européenne |

SmartTicket informe le Client de tout changement prévu concernant l'ajout ou le
remplacement d'un sous-traitant ultérieur, donnant au Client la possibilité d'émettre des
objections. Aucune donnée n'est transférée hors de l'Union européenne dans le cadre de ces
sous-traitances.

## 4. Sécurité et violation de données

SmartTicket notifie au Client toute violation de données à caractère personnel dans les
meilleurs délais après en avoir pris connaissance, et lui fournit toute information utile
pour lui permettre, le cas échéant, de notifier cette violation à l'autorité de contrôle
compétente et, si nécessaire, aux personnes concernées.

## 5. Droits des personnes concernées

Le service SmartTicket fournit nativement aux utilisateurs finaux les moyens d'exercer
leurs droits :

- **Accès** : consultation des données du compte depuis l'espace utilisateur
- **Rectification** : modification du nom d'utilisateur, email, prénom, nom
- **Portabilité** : export des données au format PDF
- **Effacement** : suppression du compte et de toutes les données associées (cascade),
  purge définitive sous 30 jours

Lorsqu'une demande est adressée directement à SmartTicket plutôt qu'au Client, SmartTicket
la transmet au Client sans délai indu, sauf s'il est en mesure d'y répondre directement via
les fonctionnalités ci-dessus.

## 6. Sort des données en fin de contrat

Au terme du contrat commercial, quelle qu'en soit la cause, SmartTicket supprime
définitivement les données du Client dans un délai de 30 jours, sauf demande expresse du
Client d'un export préalable (fonctionnalité native de la plateforme) ou obligation légale
de conservation contraire.

## 7. Documentation et audit

Sur demande raisonnable du Client, SmartTicket met à disposition les éléments démontrant sa
conformité au présent accord et permet la réalisation d'un audit, dans des conditions de
délai, de forme et de confidentialité à convenir entre les Parties.

## 8. Contact

Pour toute question relative au présent accord ou à la protection des données :
[EMAIL DE CONTACT / DPO À COMPLÉTER].

---

*Document généré comme brouillon de travail — à faire relire par un avocat spécialisé
RGPD/SaaS et à compléter avec l'identité légale de l'entité avant signature avec un client.*
