# 🤝 GUIDE DE CONTRIBUTION - NEXUS AI TRADING SYSTEM

## 📋 **Introduction**

Merci de votre intérêt pour contribuer à **NEXUS AI TRADING SYSTEM** ! 🚀

Ce guide vous aidera à comprendre comment contribuer efficacement au projet. Nous valorisons toutes les formes de contribution, qu'il s'agisse de :

- 🐛 **Rapports de bugs**
- 💡 **Suggestions de fonctionnalités**
- 📝 **Documentation**
- 🧪 **Tests**
- 💻 **Code**

---

## 📜 **Code de Conduite**

En contribuant à ce projet, vous acceptez de respecter notre **[Code de Conduite](CODE_OF_CONDUCT.md)** .

---

## 🚀 **Comment contribuer**

### 1️⃣ **Signaler un bug**

Si vous trouvez un bug, veuillez :

1. **Vérifier** que le bug n'a pas déjà été signalé
2. **Créer** une issue avec le template **Bug Report**
3. **Fournir** autant de détails que possible :
   - Version du système
   - Étapes pour reproduire
   - Comportement attendu
   - Comportement observé
   - Logs ou captures d'écran

### 2️⃣ **Proposer une fonctionnalité**

Pour proposer une nouvelle fonctionnalité :

1. **Vérifier** que la fonctionnalité n'est pas déjà prévue
2. **Créer** une issue avec le template **Feature Request**
3. **Expliquer** clairement le besoin et l'utilisation
4. **Discuter** de l'implémentation avec l'équipe

### 3️⃣ **Contribuer au code**

#### Prérequis

```bash
# Vérifier les versions
python --version  # >= 3.12
node --version    # >= 20.0
docker --version  # >= 24.0
git --version     # >= 2.0
```

#### Processus

```bash
# 1. Fork le projet
# 2. Cloner votre fork
git clone git@github.com:VOTRE_USERNAME/NEXUS-AI-TRADING-SYSTEM.git
cd NEXUS-AI-TRADING-SYSTEM

# 3. Créer une branche
git checkout -b feature/ma-fonctionnalite
# OU
git checkout -b fix/mon-correction

# 4. Installer les dépendances
./init_project.sh

# 5. Faire vos modifications
# ...

# 6. Tester
pytest
yarn test

# 7. Formater le code
black .
isort .
prettier --write .

# 8. Linter
flake8 .
eslint .
mypy .

# 9. Commit
git add .
git commit -m "feat: ajout de ma fonctionnalité"
# OU
git commit -m "fix: correction de mon bug"

# 10. Push
git push origin feature/ma-fonctionnalite

# 11. Créer une Pull Request
```

---

## 🏗️ **Standards de code**

### Python

```python
# ✅ Bon exemple
from typing import Optional

def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0
) -> Optional[float]:
    """
    Calcule le ratio de Sharpe.

    Args:
        returns: Liste des rendements
        risk_free_rate: Taux sans risque

    Returns:
        Ratio de Sharpe ou None
    """
    if not returns:
        return None
    # ...

# ❌ Mauvais exemple
def calc(x,y):
    return x/y
```

**Standards :**
- ✅ PEP 8
- ✅ Type hints
- ✅ Docstrings
- ✅ 100% test coverage
- ✅ Black formatting
- ✅ Isort imports

### TypeScript / JavaScript

```typescript
// ✅ Bon exemple
interface User {
  id: string;
  email: string;
  createdAt: Date;
}

const getUserById = async (id: string): Promise<User | null> => {
  try {
    const user = await db.users.findOne({ id });
    return user;
  } catch (error) {
    console.error('Error fetching user:', error);
    return null;
  }
};

// ❌ Mauvais exemple
function getUser(id) {
  return db.users.findOne({ id });
}
```

**Standards :**
- ✅ ESLint
- ✅ Prettier
- ✅ Type safety
- ✅ 100% test coverage
- ✅ React best practices

---

## 📁 **Structure des commits**

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Description | Emoji |
|------|-------------|-------|
| `feat` | Nouvelle fonctionnalité | ✨ |
| `fix` | Correction de bug | 🐛 |
| `docs` | Documentation | 📚 |
| `style` | Style/UI | 🎨 |
| `refactor` | Refactorisation | ♻️ |
| `perf` | Performance | ⚡ |
| `test` | Tests | 🧪 |
| `chore` | Maintenance | 🔧 |
| `ci` | CI/CD | ⚙️ |
| `security` | Sécurité | 🔒 |

### Exemples

```bash
# Nouvelle fonctionnalité
feat(backend): ajout du moteur de prédiction LSTM

# Correction de bug
fix(websocket): reconnexion automatique après déconnexion

# Documentation
docs(api): mise à jour de la documentation Swagger

# Refactorisation
refactor(risk): simplification du circuit breaker
```

---

## 📝 **Conventions de nommage**

### Branches

```yaml
feature/ma-fonctionnalite    # Nouvelles fonctionnalités
fix/mon-correction           # Corrections de bugs
hotfix/mon-hotfix            # Corrections urgentes
chore/ma-tache               # Tâches de maintenance
docs/ma-documentation        # Documentation
test/mes-tests               # Tests
```

### Fichiers

```yaml
Python:
  - snake_case.py
  - test_snake_case.py

TypeScript:
  - PascalCase.tsx
  - camelCase.ts
  - test-camelCase.ts

Configuration:
  - .eslintrc.json
  - .prettierrc
  - docker-compose.yml

Documentation:
  - README.md
  - CONTRIBUTING.md
  - CHANGELOG.md
```

---

## 🧪 **Tests**

### Exécuter les tests

```bash
# Backend
pytest
pytest --cov=backend
pytest -v
pytest -m "not integration"

# Frontend
yarn test
yarn test:coverage
yarn test:watch

# E2E
yarn test:e2e
yarn test:e2e:headed
```

### Écrire des tests

```python
# ✅ Bon exemple
import pytest
from app.services import calculate_sharpe_ratio

def test_calculate_sharpe_ratio_success():
    returns = [0.1, -0.05, 0.08, 0.02]
    result = calculate_sharpe_ratio(returns)
    assert result is not None
    assert result > 0

def test_calculate_sharpe_ratio_empty():
    result = calculate_sharpe_ratio([])
    assert result is None

# ❌ Mauvais exemple
def test_sharpe():
    assert calculate_sharpe_ratio([0.1, -0.05, 0.08, 0.02]) == 0.5
```

---

## 📚 **Documentation**

### Types de documentation

1. **Code** - Docstrings, commentaires
2. **API** - Swagger/OpenAPI
3. **Utilisateur** - Guides, tutoriels
4. **Développeur** - Architecture, setup

### Exemples

```python
# ✅ Bon exemple
def place_order(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market"
) -> dict:
    """
    Place un ordre sur le marché.

    Args:
        symbol: Symbole de trading (ex: "BTCUSDT")
        side: Direction (BUY/SELL)
        quantity: Quantité à trader
        order_type: Type d'ordre (market/limit)

    Returns:
        dict: Informations sur l'ordre

    Raises:
        OrderError: Si l'ordre est invalide
        BrokerError: Si le broker est indisponible

    Example:
        >>> place_order("BTCUSDT", "BUY", 0.01, "market")
        {"id": "123", "status": "filled"}
    """
    # ...

# ❌ Mauvais exemple
def place_order(symbol, side, quantity, order_type="market"):
    # Place un ordre
    ...
```

---

## 🔧 **Outils recommandés**

### Éditeurs

- **VS Code** - Recommandé
  - Extensions : Python, ESLint, Prettier, Docker
- **Cursor AI** - Idéal pour l'IA
- **PyCharm** - Alternative

### Linters / Formatters

```bash
# Python
black .          # Format
isort .          # Imports
flake8 .         # Lint
mypy .           # Type checking
ruff .           # Fast linting

# TypeScript
prettier --write .  # Format
eslint .            # Lint
tsc --noEmit        # Type checking

# Général
pre-commit run --all-files  # Pre-commit hooks
```

---

## 🚀 **Workflow Git**

### Commits fréquents

```bash
# ✅ Bien
git commit -m "feat(api): ajout du endpoint /health"
git commit -m "feat(api): ajout des tests pour /health"
git commit -m "docs(api): documentation de /health"

# ❌ Mal
git commit -m "fix"
git commit -m "update"
git commit -m "wip"
```

### Messages de commit

```yaml
✅ Clarifier le "quoi" et le "pourquoi"
✅ Utiliser l'impératif présent
✅ Premier ligne <= 72 caractères
✅ Corps de message pour plus de détails
✅ Référencer les issues si nécessaire

📝 Exemple:
feat(auth): ajout du login avec Google

- Intégration OAuth2
- Création automatique du compte
- Refresh tokens

Fixes #123
```

---

## 🔍 **Revue de code**

### Critères de revue

- ✅ Le code fonctionne-t-il ?
- ✅ Les tests sont-ils passés ?
- ✅ Le code est-il bien documenté ?
- ✅ Les standards sont-ils respectés ?
- ✅ Y a-t-il des problèmes de performance ?
- ✅ La sécurité est-elle prise en compte ?

### Processus

1. **Ouverture** de la PR
2. **CI** automatique (tests, lint)
3. **Revue** par au moins 2 mainteneurs
4. **Modifications** si demandées
5. **Approbation** de la PR
6. **Merge** dans main

---

## 📊 **Labels des issues**

### Types

| Label | Description |
|-------|-------------|
| `bug` | Problème signalé |
| `feature` | Nouvelle fonctionnalité |
| `enhancement` | Amélioration d'existante |
| `documentation` | Documentation |
| `tests` | Tests |
| `security` | Sécurité |
| `performance` | Performance |

### Priorités

| Label | Description |
|-------|-------------|
| `priority: high` | Urgent |
| `priority: medium` | Important |
| `priority: low` | Optionnel |

### Statuts

| Label | Description |
|-------|-------------|
| `status: ready` | Prêt à commencer |
| `status: in-progress` | En cours |
| `status: review` | En revue |
| `status: done` | Terminé |
| `status: blocked` | Bloqué |

---

## 👥 **Rôles**

### Mainteneurs

- **Responsables** du projet
- Approuvent les PR
- Gèrent les releases
- Animent la communauté

### Contributeurs

- **Actifs** - Contributions régulières
- **Occasionnels** - Contributions ponctuelles
- **Premiers** - Nouvelles contributions

---

## 📝 **Checklist de contribution**

### Avant la PR

- [ ] Code fonctionnel
- [ ] Tests passés
- [ ] Tests ajoutés/mis à jour
- [ ] Documentation mise à jour
- [ ] Code formaté
- [ ] Linting passé
- [ ] Pas de conflits
- [ ] Pas de secrets

### Après la PR

- [ ] CI passé
- [ ] Revue approuvée
- [ ] Merge effectué
- [ ] Release planifiée

---

## 🎯 **Objectifs de contribution**

### Niveaux

```yaml
Débutant:
  - Documentation
  - Tests
  - Bug fixes simples

Intermédiaire:
  - Nouvelles fonctionnalités
  - Refactorisation
  - Intégrations

Avancé:
  - Architecture
  - Performance
  - Sécurité
  - Core features
```

---

## 📞 **Besoin d'aide ?**

### Contact

```yaml
📧 Dev: dev@nexustradingia.com
📧 Support: support@nexustradingia.com
💬 Discord: https://discord.gg/nexustradingia
📱 Telegram: https://t.me/NexusTradingIA
🐦 X: https://x.com/NexusTradingIA
```

### Documentation

```yaml
📚 Documentation: https://docs.nexustradingia.com
📖 API: https://api.nexustradingia.com/docs
📝 Guides: https://docs.nexustradingia.com/guides
```

---

## 🙏 **Remerciements**

Merci à tous les contributeurs qui font vivre ce projet !

---

## 📄 **Licence**

Copyright © 2026 NEXUS QUANTUM LTD - Tous droits réservés.

---

**Dernière mise à jour :** 2026-01-15
**Version :** 1.0.0
```

---


**📝 CONTRIBUTING.md complet prêt à être utilisé !** 🚀
