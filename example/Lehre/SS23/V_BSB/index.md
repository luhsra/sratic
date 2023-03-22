---
id: lehre-ss23-V_BSB
type: lecture
title: "Betriebssystembau"
short_title: Betriebssystembau
menu.append:
  - label: Betriebsystembau
  - title: Doxygen Documentation
    href: 'doc/'
staff: [dietrich]
email: "christian.dietrich@tuhh.de"
studip: [['Betriebssystembau', 'fcd0ada885373a38513ca0928ab74bc1']]
---
{% import 'person.jinja' as person %}
{% import 'lehre.jinja' as lehre %}

# {{ page.title }} und Betriebssystembau für Einkernsysteme

<div class="well" markdown=1>

**Art der Veranstaltung**: Vorlesung/Übung<br/>
**Semester**: Sommersemester, 2V+4Ü<br/>
**Dozent/Dozent**: [[dietrich]]<br/>
**Prüfungsform**: Mündliche Prüfung<br/>
**Leistungspunkte:** 6 LP <br/>
**E-Mail**: [{{page.email}}](mailto:{{page.email}})<br/>
**Vorlesung**: Dienstag 16:15 - 17:45 Uhr (VER/N - 0009)<br/>
**Übung**: Mittwoch 9:45 bis 13:30 Uhr (HÜ: VER/N - 0005, RÜ: CIP/E  2.024P3c)<br/>
**StudIP-Veranstaltung**: {{ lehre.studip_link("BSB", page.studip[0][1]) }}<br/>
**Modul "Betriebssystembau" (Master)**:<br/>

- Master "Computer Science": **Vertiefung I. Computer- und Software-Engineering**
- Master "Informatik-Ingenieurwesen": **Technischer Ergänzungskurs (TEK)**

**Modul "Betriebssystembau für Einkernsysteme" (Bachelor)**:<br/>

- Bachelor "Computer Science": **Vertiefung I. Computer- und Software-Engineering**
- Bachelor "Informatik-Ingenieurwesen": **Vertiefung I. Informatik**
</div>

Die Veranstaltung kann entweder im Bachelor oder im Master belegt werden. 

Bei Fragen können Sie uns jederzeit eine E-Mail schreiben. Betreut wird
Betriebssystembau von [[dietrich]].

{{ person.list(['dietrich']) }}

## Inhalt der Vorlesung

Ziel der Vorlesung ist die Vermittlung von konzeptionellen Grundlagen und wichtigen Techniken, die für den Bau eines Betriebssystems erforderlich sind. In den vorlesungsbegleitenden Übungen werden diese Kenntnisse praktisch angewendet, indem ein kleines PC-Betriebssystem in kleinen Arbeitsgruppen von Grund auf neu entwickelt wird. Um dies zu bewerkstelligen, sind fundierte Kenntnisse über Aufbau und Funktionsweise der PC-Hardware erforderlich, die ebenfalls in der Lehrveranstaltung vermittelt werden. Dabei werden gleichzeitig Grundlagen aus dem Betriebssystembereich wie Unterbrechungen, Synchronisation und Ablaufplanung, die aus anderen Veranstaltungen weitgehend bekannt sein sollten, wiederholt und vertieft.

Die Vorlesung umfasst folgende Themen:

 - Grundlagen der Betriebssystementwicklung
 - Unterbrechungen (Hardware, Software, Synchronisation)
 - IA-32: Die 32-Bit-Intel-Architektur
 - Koroutinen und Programmfäden
 - Scheduling
 - Betriebssystem-Architekturen
 - Fadensynchronisation
 - Gerätetreiber
 - Interprozesskommunikation

## Organisation und Inhalt der Übungen

Ziel der Übungen ist es, schrittweise ein kleines Betriebssystem für
den PC zu entwickeln. Für die Bearbeitung der Übungsaufgaben werden
Gruppen von je 2 Studierenden gebildet. Dabei gibt es zwei Varianten der Übung:

- **OOStuBS** ist die klassische Uniprozessorvariante
- **MPStuBS** ist die Variante für moderne Mehrkernrechner

Die Teilnahme an den Übungen, sowie die Abgabe der Übungsaufgaben ist
**verpflichtend**. Falls Sie alle Übungsaufgaben für erfolgreich
abgeben, erhalten Sie einen Bonus von *10 %* auf Ihre Modulnote.

In den Tafelübungen werden Fragen zum Stoff der Vorlesung geklärt und
die Übungsaufgaben vorgestellt. Zusätzlich werden Hintergründe, die
für die Aufgaben relevant sind, stärker beleuchtet (z.B.
Hardware-Spezifika), Knackpunkte im Design und der Implementierung
zusammen besprochen und Lösungen entwickelt. Da die Bearbeitung einer 
Aufgabe in der Regel zwei Wochen beansprucht, finden Tafelübungen nicht 
wöchentlich statt (siehe Semesterplan).


## Technische Infrastruktur

Aufgrund der aktuellen Lage sind die Computerpools nicht zugänglich, daher
sind hier die Möglichkeiten an die Infrastruktur und Software zu kommen
ausgelistet:

- Fernzugrgriff auf den [Linux-Pool](https://www.tuhh.de/rzt/studium/pools.html)
  - Konsole per SSH
  - Graphische Oberfläche per X2Go
- Installation der Software auf einem eigenen PC

Auch wenn die Computerpools gerade nicht zugänglich sind, sind wir für
auftauchende Fragen und Probleme da. Weiteres wird in der Übung und
Vorlesung bekannt gegeben.

### Eigener PC

Für die Installation auf dem eigenen PC wird folgende Software benötigt:

* QEMU (qemu, qemu-system-x86, qemu-kvm)
* GCC (build-essentials, binutils, gcc-multilibs, g++)
* nasm

Für Ubuntu (20.04):
```
apt install nasm qemu qemu-system-x86 qemu-kvm build-essential binutils gcc-multilib g++
```

## Vorläufiger Semesterplan

{% yaml as Vorlesung %}
1: Einführung
2: BS-Entwicklung
3: IRQs (Hardware)
4: IRQs (Software)
5: Intel IA-32
6: IRQs (Synchronisation)
7: Koroutinen und Fäden
8: Scheduling
9: Architekturen
10: Fadensynchronisation
11: Gerätetreiber
12: Ausblick
E2: "Extra: Externer Vortrag um 15:00"
E1: "Extra: Meltdown & Spectre"
{% endyaml %}
{% yaml as Ubung %}
0: C++
1: Ein-/Ausgabe
2: IRQ-Behandlung
3: IRQ-Synchronisation
4: Fadenumschaltung
5: Zeitscheiben-Scheduling
6: Fadensynchronistion
7: Anwendung (opt)
{% endyaml %}

{%macro V(n)%}<span class="badge bg-primary">VL{{n}}</span><span class="badge bg-secondary">{{Vorlesung[n]}}</span>{%endmacro%}
{%macro U(n)%}<span class="badge bg-success">Ü{{n}}</span><span class="badge bg-secondary">{{Ubung[n]}}</span>{%endmacro%}

{%macro R() %}<span class="badge bg-warning">RÜ</span>{%endmacro%}
{%macro A(n) %}<span class="badge bg-danger">A{{n}}</span><span class="badge bg-secondary">Abgabe {{n}}</span>{%endmacro%}

| KW   | Dienstag  | Di 16:15  | Mi 9:45  | Mi 11:15 | Späteste Abgabe |
|------|-----------|-----------|----------|----------|-----------------|
| KW14 | 4. April  | entfällt  | entfällt | entfällt |
| KW15 | 11. April | {{V(1)}}  | {{V(2)}} | {{U(0)}} |                 |
| KW16 | 18. April | {{V(3)}}  | {{U(1)}} | {{R()}}  |                 |
| KW17 | 25. April | {{V(4)}}  | {{R()}}  | {{R()}}  |                 |
| KW18 | 02. Mai   | {{V(5)}}  | {{U(2)}} | {{R()}}  | {{A(1)}}        |
| KW19 | 09. Mai   | {{V(6)}}  | {{U(3)}} | {{R()}}  |                 |
| KW20 | 16. Mai   | Ferien    |          |          |                 |
| KW21 | 23. Mai   | {{V(7)}}  | {{R()}}  | {{R()}}  | {{A(2)}}        |
| KW22 | 30. Mai   | {{V(8)}}  | {{U(4)}} | {{R()}}  | {{A(3)}}        |
| KW23 | 06. Juni  | {{V(9)}}  | {{R()}}  | {{R()}}  |                 |
| KW24 | 13. Juni  | {{V(10)}} | {{U(5)}} | {{R()}}  | {{A(4)}}        |
| KW25 | 20. Juni  | {{V(11)}} | {{R()}}  | {{R()}}  |                 |
| KW26 | 27. Juni  | {{V(12)}} | {{U(6)}} | {{R()}}  | {{A(5)}}        |
| KW27 | 04. Juli  | (Ersatz)  | {{U(7)}} | {{R()}}  |                 |
| KW28 | 11. Juli  | (Ersatz)  | {{R()}}  | {{R()}}  | {{A(6)}}        |



Die optionale Übung 0 bietet eine kurze Einführung in
betriebssystemspezifisches C++. Die Abgabe findet in den
Rechnerübungen durch gemeinsame Diskutieren der Lösung statt.

## Vorkenntnisse

- Grundlagen aus dem Betriebssystembereich wie Unterbrechungen,
  Synchronisation und Ablaufplanung aus früheren Veranstaltungen (Betriebssysteme)
    - Wiederholung und Vertiefung in Vorlesung und Übung
- C / **C++** und Assembler (x86)
    - Betriebssystemspezifische Inhalte werden in den Übungen vermittelt.
    - Hilfe bei Bedarf

## Evaluation

{{ lehre.evaluation('V_BSB') }}


{{ lehre.studip() }}
