---
id: theses
title: Theses (BA/MA)
parent: main
menu.parent: true
---

This list is just a collection of thesis ideas that were already formulated.
We always have more interesting ideas, which were not written down yet, on the topics *operating systems*, *real-time systems*, *dependability*,  *software variability*, etc.
So, if this list is empty, you find none of the presented thesis ideas interesting, or you have this one brilliant idea you want to pursue, just come around or write a mail.

Open Topics
============================

{% if object_list('thesis', status=['open']) %}
{{ show.list('thesis', status=['open']) }}
{% else %}
There are currently no theses advertised. If you have an idea for a topic, feel free to contact us. 😃
{% endif %}

{% if object_list('thesis', status=['running', 'reserved']) %}

Running Theses
===============================

{{ show.list('thesis', status=['reserved', 'running']) }}
{% else %}
{% endif %}

{% if object_list('thesis', status=['finished']) %}

Finished Theses
================================

{{ show.list('thesis', status=['finished']) }}
{% else %}
{% endif %}

{% if False %}
Thesis Template
===============================

{% endif %}
