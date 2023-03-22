---
id: ParPerOS
type: project
parent: research
depends: theses
short_title: ParPerOS
title: "Parallel Persistency OS (DFG: DI 2840/2-1)"
project-status: running
summary: >-
  In ParPerOS, we examine new abstractions for unified but efficient and optionally crash-consistent low-level memory management for data objects in heterogeneous memory systems that consist of volatile, persistent, distributed and other types of main memory.
---

{% import 'project.jinja' as project %}
{% import 'person.jinja' as person %}
{% from 'navigation.jinja' import biblink as bib %}

{{ project.makeheader(page) }}


## People ##

{{ person.list(['dietrich']) }}


{{ project.makefooter(page) }}
