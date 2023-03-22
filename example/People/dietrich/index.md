---
type: person
id:   dietrich
parent: people
name-prefix: Prof. Dr.-Ing.
name: Christian Dietrich
image: !path dietrich.png
room: Am Schwarzenberg 3 (E), 4.092
job: Juniorprofessor
phone: +49 40 42878 2188
mail: christian.dietrich@tuhh.de
data:
   important-papers:
    - "leis:23:sigmod"
---
{% import 'person.jinja' as person %}

{% call person.makeheader(page) %}
{# Add Extra Text here #}

{% endcall %}

## Projects {#projects }

{{ show.show('ATLAS') }}
{{ show.show('ParPerOS') }}


# Teaching and Courses

{{ show.show_lectures(page.id) }}


## Publications { #publications }

{% for year, list in object_list('publication', author='Christian Dietrich') | groupby('bibtex.year') | reverse%}
<h3>{{year}}</h3>
  {% for pub in list %}
      {% if pub.id in page.data["important-papers"] %}
         <div class="indicator-green">
         {{ show.show(pub) }}
         </div>
      {% else %}
         {{ show.show(pub) }}
      {% endif %}
  {% endfor%}
{% endfor%}

