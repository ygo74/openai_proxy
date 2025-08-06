# FastAPI OpenAI Proxy

This project is a FastAPI-based proxy for OpenAI. It provides a simple interface to interact with OpenAI's API.


# sources

transparent proxy : https://github.com/fangwentong/openai-proxy
OpenAI schema : https://github.com/openai/openai-openapi/blob/manual_spec/openapi.yaml

# development

## Start backends

``` powershell
docker compose -f .\docker-compose-backend.yml up -d

```

## start the service

``` powershell
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

```

# Azure configuration

Pour pouvoir lister les modèles déployés sur Azure via l’API REST que tu mentionnes, il te faut une authentification OAuth 2.0 avec Azure Active Directory (AAD). Voici comment procéder étape par étape pour intégrer cela dans une API :

## 🔐 Étapes pour s'authentifier sur Azure via une API

1. Enregistrer ton application dans Azure AD
Va sur Azure Portal

Navigue vers Azure Active Directory > App registrations

Clique sur New registration

Note le Client ID (Application ID) et le Tenant ID

2. Créer un secret ou certificat pour l’application
Dans ton application enregistrée > Certificates & Secrets

Crée un secret client (Client Secret) et sauvegarde sa valeur

3. Attribuer les autorisations API
Dans ton application > API permissions

Ajoute l’autorisation Azure Service Management > user_impersonation (ou selon l’API utilisée)

Clique sur Grant admin consent si nécessaire

## 🔍 Étapes pour le retrouver dans le portail Azure
Connecte-toi au portail Azure

Dans le menu de gauche, clique sur Abonnements (ou cherche "Subscriptions" dans la barre de recherche)

Tu verras la liste de tes abonnements. L’ID d’abonnement est affiché dans la deuxième colonne

Tu peux aussi cliquer sur le nom de l’abonnement pour voir plus de détails et copier l’ID facilement

## 🔐 Étapes pour donner accès au service azure openai

1. Vérifie que ton application a bien le rôle requis
Tu dois attribuer à ton application Azure AD un rôle sur la ressource Azure OpenAI. Voici comment faire :

Va sur Azure Portal

Navigue vers la ressource Azure OpenAI

Clique sur Contrôle d’accès (IAM) dans le menu de gauche

Clique sur Ajouter un rôle

Sélectionne le rôle Lecteur ou Cognitive Services Contributor

Dans la section Membre, choisis Identité managée ou application et sélectionne ton application
