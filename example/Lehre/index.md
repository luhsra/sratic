---
id: lehre
title: Teaching
parent: main
menu.parent: true
menu.append:
   - label: Semester
   - lehre-ss23
---
{% import 'lehre.jinja' as lehre %}

<h1>Master Courses</h1>

<div class="row">
  <div class="col-lg-6">
    <div class="lehre-bs">
      <strong>Summersemester</strong>
      {{ lehre.lecture('Betriebssystembau', 'lehre-V_BSB', 'BSB') }}
    </div>
  </div>
</div>

