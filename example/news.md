---
parent: main
id: news
title: News Archive
menu.list: false
data: !include news.myml
---

{% for item in object_list('news') | sorted | reverse %}
{{ show.show(item) }}
{% endfor %}
