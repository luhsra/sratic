---
id: ATLAS
type: project
parent: research
depends: theses
short_title: ATLAS
title: "Adaptable Thread-Level Address Spaces (DFG: DI 2840/1-1)"
project-status: running
summary: >-
  In the ATLAS project, we investigate dynamic specialization and containment by means of thread-level address-space variations.
---

{% import 'project.jinja' as project %}
{% import 'person.jinja' as person %}
{% from 'navigation.jinja' import biblink as bib %}

{{ project.makeheader(page) }}

## People ##

{{ person.list(['dietrich']) }}

{{ project.makefooter(page) }}
