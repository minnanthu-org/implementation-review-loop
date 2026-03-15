---

# Coding Rules

## Purpose

This repository prioritizes clean design and code simplicity over minimal patching.
Agents must avoid incremental patching that preserves outdated structures.

The goal is correct architecture and maintainable code, not minimal diffs.

---

# Core Principles

## 1. Do not prioritize minimal diffs

Do not treat existing code as something that must be preserved.

When modifying code:

* Prefer clear architecture over minimal edits
* Prefer refactoring over patching
* Prefer replacement over extension when structure is wrong

Minimal change is not a goal.

---

## 2. Remove dead code aggressively

Agents must actively remove:

* unused functions
* unused parameters
* obsolete branches
* legacy compatibility code
* duplicate implementations

Do not leave old code in place just in case.

If functionality is replaced, delete the old implementation.

---

## 3. Avoid dual implementations

Do not allow:

* old API + new API
* old logic + new logic
* temporary compatibility layers

If a new approach is introduced, fully migrate to it.

---

## 4. Prefer redesign over incremental fixes

When the current structure is problematic:

1. Propose a clean design
2. Then implement it

Do not attempt to patch around structural problems.

---

## 5. Simplify responsibility boundaries

Agents should reduce complexity by:

* merging unnecessary abstractions
* removing redundant layers
* simplifying control flow
* reducing configuration where possible

The preferred outcome is less code, not more code.

---

## 6. Report deletions

When modifying code, agents should explicitly state:

* what code was removed
* why it was removed
* what replaces it if applicable

Deletion is considered a positive outcome.

---

## 7. Code health over backward compatibility

Backward compatibility should not be preserved automatically.

Only maintain compatibility if explicitly required.

Otherwise prefer:

* simpler APIs
* clearer behavior
* fewer legacy constraints

---

## 8. Target outcome

The desired result of a change is typically:

* fewer lines of code
* fewer abstractions
* fewer branches
* clearer responsibilities

Large deletions are often a sign of success.