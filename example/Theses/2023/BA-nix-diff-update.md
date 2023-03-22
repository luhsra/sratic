---
id: "BA-nix-diff-update"
title: "NixDiff: Offline Compression of Differential Updates for Declaratively-Configured Embedded Linux Systems"
parent: theses
type: thesis
thesis-type: BA
thesis-supervisor: [ dietrich]
thesis-status: running
# thesis-student: Max Mustermann
thesis-start: !!timestamp 2023-01-01
thesis-end:   !!timestamp 2021-03-31 # TODO: adjust once registered
summary: "Decrease the size of NixOS updates, especially for embedded systems, by removing redundant file blocks from the transferred packages"
projects: []
---
{% import 'thesis.jinja' as thesis %}
{{ thesis.maketitle(page) }}

The Nix package manager, and thus the NixOS Linux distribution based on it, stores its packages not merged as a single File System Hierarchy compliant directory tree, but side-by-side in per-package directories.
Each of these directory's names includes a hash over either the directory content, or the inputs that were used to create its contents.
This has the advantage that any number and type of package, including different versions and variants of the same package, but also (the packages of) different versions or configurations of complete NixOS installations, can be stored at the same time, and are deduplicated if they are identical.

Nix packages pin the versions of their runtime dependencies by including the full path of their dependencies in their build outputs.
While this is great for reproducibility and to avoid dependency conflicts at runtime, changing a base dependency thus changes the file contents and thus hash and storage-path of all dependents, recursively.
As a consequence of this ripple, semantically small changes, especially if they affect packages with many dependents, can cause many packages to change.
Nix's default approach to re-download or rebuild each changed package is not appropriate in bandwidth, storage, or otherwise resource constrained environments.

This thesis evaluates approaches to reduce the update sizes, by reusing information from packages, files and file segments whose content -- semantically or approximately -- is already present on the target.
A [previous thesis](../2022/MA-Light-Weight-Containers.html) has done this to the point of reusing files that were present with identical content in packages before the update.
This thesis uses existing tools, as well as approaches tailored to the specificities of Nix package updates, to find and reuse same and similar content even within files.
These approaches are compared and evaluated in their efficiency when executed on different NixOS upgrades.
