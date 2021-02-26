---
type: person
id:   mustermann
parent: people
name-postfix: M.Sc.
name: Max Mustermann
image: !path mustermann.png
job: Wissenschaftlicher Mitarbeiter
phone: 0511 762 19XXX
mail: mustermann@sra.uni-hannover.de
room: 120
---
{% import 'person.jinja' as person %}

{% call person.makeheader(page) %}
{# Add Extra Text here #}
{% endcall %}

## Projects {#projects }

{{ show.show('AHA') }}

{# Uncomment, if applicable #}
{# ## Past Projects #}

## Teaching and Courses

- Winter 2017/2018: [[lehre-ws17-L_BST]]
- Summer 2017: [[lehre-ss17-V_BSB]], [[lehre-ss17-L_KHP]]

{# Uncomment, if applicable #}
{# ## Awards und Grants #}


{% if false %}
## Publications { #publications }
{% for year, list in object_list('publication', author='Christian Dietrich') | groupby('bibtex.year') | reverse%}
<h3>{{year}}</h3>
  {% for pub in list %}
     {{show.show(pub)}}
  {% endfor%}
{% endfor%}

## Supervised Theses { #theses}
### Open Theses Topics ###
{{ show.list('thesis', status=['open'], supervisor=page.id) }}

### Finished Student Theses ###
{{ show.list('thesis', status=['finished'], supervisor=page.id, show_list=True) }}

{% endif %}
