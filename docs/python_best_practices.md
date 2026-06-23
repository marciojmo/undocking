---
description: Python best practices and conventions
globs: "**/*.{py}"
alwaysApply: false
---
# Python Best Practices

A practical set of Python engineering guidelines based primarily on the Google Python Style Guide.

---

# Core Principles

* Optimize for readability and maintainability.
* Write code for the next engineer, not just for the computer.
* Prefer explicit code over clever code.
* Consistency is more important than personal preference.
* Favor simplicity over conciseness.

---

# Project Structure

## Organize Code Into Small Modules

Keep modules focused on a single responsibility.

**Good**

```python
user_service.py
user_repository.py
user_validator.py
```

**Avoid**

```python
utils.py
helpers.py
common.py
```

Large generic modules become dumping grounds and are difficult to maintain.

---

# Imports

## Import Order

Group imports in the following order:

1. Standard library
2. Third-party packages
3. Local application imports

```python
import datetime
import json

import requests

from myapp.services import user_service
```

## Import Modules Instead of Individual Members

Prefer:

```python
import statistics

average = statistics.mean(values)
```

Over:

```python
from statistics import mean

average = mean(values)
```

Exception: commonly accepted imports are acceptable.

```python
import numpy as np
import pandas as pd
```

## Avoid Wildcard Imports

Never:

```python
from module import *
```

Use explicit imports instead.

---

# Naming Conventions

## Variables and Functions

Use snake_case.

```python
user_count = 10

def calculate_total():
    pass
```

## Classes

Use PascalCase.

```python
class UserRepository:
    pass
```

## Constants

Use UPPER_CASE_WITH_UNDERSCORES.

```python
MAX_RETRY_ATTEMPTS = 3
```

## Protected Members

Prefix with a single underscore.

```python
_internal_cache = {}
```

## Avoid

* Single-character names outside small loops.
* Names that include type information.

Bad:

```python
user_list
id_to_name_dict
```

Better:

```python
users
user_names
```

---

# Functions

## Keep Functions Small

Functions should do one thing.

Bad:

```python
def process_user():
    validate()
    save()
    send_email()
    generate_report()
```

Better:

```python
def process_user():
    validate_user()
    save_user()
```

## Prefer Descriptive Names

Bad:

```python
def calc(x, y):
    pass
```

Better:

```python
def calculate_discount(price, percentage):
    pass
```

## Type Annotate Public APIs

```python
def calculate_total(price: float, tax: float) -> float:
    return price + tax
```

---

# Type Hints

Use type annotations for new code.

```python
def find_user(user_id: int) -> User:
    ...
```

Prefer built-in generics:

```python
def get_names() -> list[str]:
    ...
```

Avoid excessive use of `Any`.

```python
from typing import Any
```

Use only when necessary.

---

# Docstrings

Use triple double quotes.

```python
def get_user(user_id: int) -> User:
    """Returns a user by ID."""
```

## Public Functions Should Have Docstrings

Document:

* Purpose
* Arguments
* Return values
* Exceptions when relevant

Example:

```python
def create_user(name: str, email: str) -> User:
    """Creates a new user.

    Args:
        name: User's display name.
        email: User's email address.

    Returns:
        The newly created user.
    """
```

---

# Comments

## Explain Why, Not What

Bad:

```python
# Increment counter
counter += 1
```

Good:

```python
# Offset by one because the API uses 1-based indexing.
counter += 1
```

## Keep Comments Updated

Outdated comments are worse than no comments.

---

# Exceptions

## Use Exceptions Appropriately

Raise exceptions for exceptional situations.

```python
if user is None:
    raise ValueError("User cannot be None")
```

## Catch Specific Exceptions

Prefer:

```python
try:
    load_file()
except FileNotFoundError:
    ...
```

Avoid:

```python
except Exception:
    ...
```

Unless rethrowing, logging, or handling application boundaries.

---

# Default Arguments

Never use mutable default arguments.

Bad:

```python
def add_user(user, users=[]):
    users.append(user)
```

Good:

```python
def add_user(user, users=None):
    if users is None:
        users = []
```

---

# Comprehensions

Use comprehensions for simple transformations.

Good:

```python
names = [user.name for user in users]
```

Avoid complex nested comprehensions.

Bad:

```python
result = [
    (x, y)
    for x in range(10)
    for y in range(10)
    if x * y > 5
]
```

Prefer explicit loops when complexity increases.

---

# Lambdas

Use lambda only for simple expressions.

Good:

```python
sorted(users, key=lambda user: user.name)
```

Prefer named functions for anything more complex.

---

# Truthiness

Prefer Pythonic truth checks.

Good:

```python
if users:
    ...
```

Instead of:

```python
if len(users) > 0:
    ...
```

Also:

```python
if value is None:
    ...
```

When distinguishing `None` from other falsy values.

---

# Properties

Use properties when access requires behavior.

```python
@property
def full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"
```

Do not use trivial getters and setters.

---

# Global State

Minimize mutable global state.

Good:

```python
MAX_RETRIES = 3
```

Avoid:

```python
current_user = None
```

Pass dependencies explicitly.

---

# Resource Management

Always use context managers.

Good:

```python
with open(path) as file:
    data = file.read()
```

Avoid:

```python
file = open(path)
...
file.close()
```

---

# Logging

Use logging instead of print statements.

```python
import logging

logger = logging.getLogger(__name__)

logger.info("User created: %s", user_id)
```

Avoid:

```python
print("User created")
```

---

# String Formatting

Prefer f-strings.

```python
message = f"User {user_id} created"
```

For logging, use parameterized formatting:

```python
logger.info("User created: %s", user_id)
```

---

# Formatting

## Line Length

Keep lines reasonably short.

Many teams use Black or Pyink for automatic formatting.

## Indentation

Use 4 spaces.

Never use tabs.

## One Statement Per Line

Good:

```python
if valid:
    process()
```

Avoid:

```python
if valid: process()
```

except in rare trivial cases.

---

# Main Entry Point

Place executable code in a main function.

```python
def main() -> None:
    run_application()


if __name__ == "__main__":
    main()
```

Avoid executing business logic at module import time.

---

# Testing

## Test Behavior, Not Implementation

Focus on observable outcomes.

## Test Naming

Use descriptive names.

```python
def test_create_user_returns_valid_user():
    ...
```

## Keep Tests Independent

Tests should not depend on execution order.

---

# Code Review Checklist

Before merging code:

* [ ] Names are descriptive.
* [ ] Public APIs have type hints.
* [ ] Public APIs have docstrings.
* [ ] No mutable default arguments.
* [ ] Exceptions are specific.
* [ ] No unnecessary global state.
* [ ] Complex logic is decomposed into functions.
* [ ] Logging is used instead of print.
* [ ] Tests exist and are meaningful.
* [ ] Imports are organized.
* [ ] Code is formatted automatically.

---

# Summary

Prioritize:

1. Readability
2. Simplicity
3. Consistency
4. Explicitness
5. Maintainability

When choosing between a clever solution and a clear solution, choose the clear solution.
