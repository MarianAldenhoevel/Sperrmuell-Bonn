TL;DR: Ein Python-Programm zur Geokodierung der Adressen zu Sperrmüll-Abfuhrterminen der Stadt Bonn

https://qvwx.de/sperrmuell-bonn-2021/Termine.html

![Beispielkarte](https://marian-aldenhoevel.de/wp-content/uploads/2021/09/Sperrmuell.jpg)

# Was ist das?

Die Stadt Bonn bietet ihren Bürgern eine regelmäßige Sperrmüllabfuhr an. Zu diesem Termin stellt man seinen Müll
an die Straße, üblicherweise am Vorabend, und am Morgen wird er von den städtischen Angestellten abgeholt.

Es gibt vielerlei Gründe für ein "Basisrecycling" an diesen Tagen: Neugier darauf was für lustige Dinge Menschen
wegwerfen. Sammeln von Wertstoffen. Beschaffung von Teilen oder Material für kommende Projekte.

Im letzten Jahrhundert bekam jeder Haushalt einmal im Jahr eine Liste zugestellt der man anhand seiner Adresse
entnehmen konnte in welchen Gebiet man wohnt und einen Stadtplan in dem diese Gebiete geographisch abgegrenzt
waren. Mit dieser Information war es trivial das Ausflugsziel "Sperrmüll" für einen gegebenen Tag zu ermitteln.

Die Stadt hat aber etwas gegen Sperrmüllausflüge, auch dafür gibt es leider gute Gründe, und hat diesen 
Ansatz abgeschafft.

Aktuell bekommt jeder Haushalt genau seine vier Termine für das Jahr postalisch mitgeteilt. Ohne Hinweis auf
andere Gebiete. Hat man den Zettel nicht aufbewahrtkann man auf einer Website seine Adresse eingeben und dort 
die Abfuhrtermine nochmal nachlesen. 

Die Rückwärtssuche vom Termin zum Gebiet ist damit kaputt. Um heute zu ermitteln wohin man seinen Ausflug soll
muss man also stichprobenweise Adressen eingeben bis das richtige Datum bei den gelisteten Terminen dabei ist. 
Und dann wenn man möchte von dort aus Adressen im Umkreis um das Gebiet abzugrenzen.

Bonn ist aber auch modern und digital und deswegen gibt es die Termine im CSV-Format zum Herunterladen.

Das Datenformat ist furchtbar - normal - und aus irgendeinem Grund mit einer Zeichenkodierung abgespeichert 
die meine Werkzeuge als "Griechisch (Macintosh)" identifizieren. Ich wusste nicht mal, dass es so etwas gibt.

Dieses Repository präsentiert ein kleines Python-Programm das aus dem Open-Data-Format zu jedem Abfuhrtermin
eine Karte erzeugt in der die Adressen markiert sind.

https://qvwx.de/sperrmuell-bonn-2021/Termine.html
