---
id: main
title: Home
heading: Fixture Site
children: [child]
formatter.output_templates: [page.html.raw]
---
# {{ page.heading }}

People: {{ object_list('person') | length }}

From CSV: {{ deref('ada').name }}

Link: [[child]]

Bibliography: {{ deref('example').title }}
