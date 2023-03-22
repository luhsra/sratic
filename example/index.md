---
id: main
title: Homepage
short_title: OSG
depends: [news]
topmenu:
  - people
  - research
  - publications-all
  - lehre
  - theses
  - kontakt
menu:
  - people
  - research
  - publications-all
  - lehre
  - theses
  - type: link
    title: Gitlab
    href: https://collaborating.tuhh.de/e-exk4
  - sitemap

lang: en
---
{%- import 'person.jinja' as person -%}

#  Operating System Group (OSG)

Our [[research]] and [[lehre]] activities are centered around
operating systems: From hardware over system software up to languages
and compilers with a focus on constructive methods for the design and
development of adaptable and versatile system software. The group is
led by [[dietrich]]


## News and Trivia <a style="float:right;margin-right:28px" href="{{ '/news.xml' | link}}"><img src="{{ '/static/img/newsicon.png' | link}}"/></a>

{% for item in object_list('news', maxage=370) | sorted | reverse %}
{{ show.show(item) }}
{% endfor %}

<center>*[[news]]*</center>
