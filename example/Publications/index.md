---
id: publications-all
title: Publications
parent: main
---
# {{ page.title }}

{% set pubs = object_list('publication', own=true) %}

{% for year, list in pubs | groupby('bibtex.year') | reverse%}
<h3>{{year}}</h3>
{% for pub in list %}
{{show.show(pub)}}
{% endfor %}
{% endfor%}
