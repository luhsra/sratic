---
id: research
title: Research
parent: main
menu:
    - title: Research Overview
    - type: anchor
      href: research
      anchor: topics
      title: Topics
    - type: anchor
      href: research
      anchor: philosophy-and-approach
      title: Approach
    - type: anchor
      href: research
      anchor: research-projects
      title: Project Map
    - title: Running Projects
    - ATLAS
    - ParPerOS
---

{% from 'navigation.jinja' import biblink as bib %}

# Research { #research }

Our research activities are centered around the **operating systems**: Between a rock and a hard place, operating systems are ocated between the hardware and application.
 We target **general-purpose abstraction** that have to cope with tight demands regarding nonfunctional properties, such as noise reduction, timeliness, robustness and hardware resources. We mostly do **fundamental research** with auxiliary funding provided by the [[DFG]].
Our Focus is on **constructive methods** for the design and development of versatile **operating systems (extensions)** that assist the application in exploiting the hardware's potential.

## Research Projects { #research-projects }

### Running Projects

{{ show.list('project', status=['running']) }}


### Finished Projects {#finished}
{{ show.list('project', status=['finished']) }}
