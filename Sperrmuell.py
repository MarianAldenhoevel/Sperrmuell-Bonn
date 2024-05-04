'''
    Dieses Python-Programm liest die von der Stadt Bonn im CSV-Format veröffentlichten Müllabfuhrtermine.
    Es sucht in der CSV-Datei nach Sperrmüllterminen und erzeugt für jeden Termin der in der Zukunft liegt
    eine Liste der Adressen, Geokoordinaten und eine OpenStreetMap-basierte interaktive Karte.

    Vorbereitung (2020 und 2021 erfolgreich):
        - Open Data herunterladen (Google "Bonn Sperrmüll Open Data"). 
        - In Libre Office Calc öffnen, dabei Zeichenkodierung Macintosh Westeuropa wählen. 
        - Copy-Paste in eine neue Libre-Office-Tabelle.
        - Als CSV in UTF-8 speichern.
        - Einstellungen unten am Beginn des Codes prüfen/aktualisieren.
        - Profit!

    2023:
        - Zeichenkodierung UTF-8, keine Konvertierung nötig.
        - Datenqualität: Spalten sind verrutscht. Workaround: Im CSV in einem Texteditor ';?;' löschen.     
'''

import os
import datetime
import json
import csv
import folium
import re
import xml.etree.ElementTree as ET

# Einen Excel-Spaltennamen in einen 0-basierten numerischen Index wandeln.
def col2num(col):
    num = 0
    for c in col:
        if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            num = num * 26 + (ord(c.upper()) - ord('A')) + 1
    return num-1

# Einstellungen ab hier:

YEAR = '2024'

# Dateiname des aktuellen CSV-Downloads:
CSV_FILENAME = 'Abfallplaner' + YEAR + '.csv'

# Spaltenindizes im CSV:
COL_TYP = col2num('N') # Spalte in der der Abfuhrtyp steht. Wir suchen "Sperrmüll"
COL_TERMIN_00 = col2num('AS')  # Spalte in der der erste Abfuhrtermin steht, Annahme: Der Rest nach rechts sind weitere Termine 

COL_STRASSE = col2num('X')    
COL_ORT = col2num('Y')
COL_PLZ = col2num('AA')
COL_HAUSNUMMER_GERADE_AB = col2num('AB')
COL_HAUSNUMMER_GERADE_BIS = COL_HAUSNUMMER_GERADE_AB + 1

COL_HAUSNUMMER_UNGERADE_AB = col2num('AD')
COL_HAUSNUMMER_UNGERADE_BIS = COL_HAUSNUMMER_UNGERADE_AB + 1

# Die Daten sagen 1-9999 bzw 2-9998 wenn die ganze Straße gemeint ist. Um nicht alle vergeblich
# abzufragen hier eine willkürlich gewählte Obergrenze die auf "ab" aufgeschlagen wird.
MAX_HAUSNUMMER_FOR_GEOLOCATION = 100

# Liste aller Abfuhrtermine als HTML-Fragment mit Links auf die Karte und andere Ausgaben speichern.
# Achtung: Dies schreibt die ganze Liste neu und fügt dabei "nebenbei" den neu geschriebenen Tag hinzu.
def saveTermine():
    with open(YEAR + '/Termine.html', 'w') as f:
        todaystr = datetime.datetime.today().strftime('%d.%m.')
        yearstr = datetime.datetime.today().strftime('%Y')
        print(f'<h1>Sperrmülltermine Bonn {yearstr} ab {todaystr}</h1>', file = f)
        print(f'<ul>', file = f)

        for termin in termine:
            foldername = termin.strftime('%Y-%m-%d')

            if os.path.exists(termin.strftime('%Y') + '\\' + foldername): # Nur erfolgreich verarbeitete
                terminstr = termin.strftime('%d.%m.%Y')
                print(f'  <li>', file = f)
                print(f'    <span>{terminstr}: </span>', file = f)
                print(f'    <a href="{foldername}/Karte.html">Karte</a> - ', file = f)
                print(f'    <a href="{foldername}/Adressen.txt">Adressen</a> - ', file = f)
                print(f'    <a href="{foldername}/Koordinaten.txt">Koordinaten</a>', file = f)          
                print(f'  </li>', file = f)

        print(f'</ul>', file = f)

# Open Street Map Karte parsen. OSM-Map.xml enthält einen großzügigen Bereich rund um
# das interessante Gebiet. Wir extrahieren alle Adressen daraus und ordnen jeder eine
# einzelne Geokoordinate zu.
#
# Koordinaten stehen als einzelnes Paar an <node>-Elementen. <way>-Elemente referenzieren
# Listen von <node>s.
#
# Also lesen wir zuerst alle Nodes. Diejenigen davon, die schon eine Adresse zugeordnet
# haben kommen direkt in die Liste. Alle werden mit ihren IDs und Koordinaten aufbewahrt.
#
# Dann iterieren wir über die Ways. Jeder, der eine Adresse bezeichnet wird als Liste
# aller seiner ref-Koordinaten abgebildet.
#
# Am Ende bilden wir einen Durchschnitt um jede Adresse auf einen einzelnen Punkt 
# einzudampfen der dann schließlich in der Karte dargestellt werden wird.
nodes = {}
addresses = {}
streetranges = {}

if True:
    print('OSM XML parsen...')
    tree = ET.parse('OSM-Map.xml')
    root = tree.getroot()

    print('OSM Adressen extrahieren...')
    def extractAddr(elem):
        addr = {}
        for tag in elem.findall('tag'): 
            if tag.attrib['k'] == 'addr:city':
                addr['city'] = tag.attrib['v']
            elif tag.attrib['k'] == 'addr:street':
                addr['street'] = tag.attrib['v']
            elif tag.attrib['k'] == 'addr:postcode':
                addr['postcode'] = tag.attrib['v']
            elif tag.attrib['k'] == 'addr:housenumber':
                addr['housenumber'] = tag.attrib['v']
        return addr

    def doAddAddr(addr, nr, coords):    
        global addresses
        global streetranges

        a = f'{addr["street"]} {nr}, {addr["postcode"]} {addr["city"]}'
        if not a in addresses:
            # Eine frische Adresse.
            addresses[a] = []
        
        # Ein neuer Koordinatenpunkt für eine Adresse.
        addresses[a] = addresses[a] + coords

        # Hausnummernbereich für diese Straße aktualisieren.
        if addr["street"] in streetranges:
            minh, maxh = streetranges[addr["street"]]
            minh = min(minh, nr)
            maxh = max(maxh, nr)     
        else:
            minh, maxh = (nr, nr)
            
        streetranges[addr["street"]] = (minh, maxh)    

    def addAddr(addr, coords):
        parts = re.split(',|;', addr['housenumber'])

        try:
            for part in parts:
                part = ''.join(ch for ch in part if ch.isdigit() or ch=='-')
                h = part.split('-', 2)
                h = [s for s in h if s]
                if len(h) == 1:
                    h.append(h[0])
            
                if h[0] == h[1]:
                    doAddAddr(addr, int(h[0]), coords)
                else:
                    for nr in range(int(h[0]), int(h[1])):    
                        doAddAddr(addr, nr, coords)
        except:
            print(f'{addr["street"]} {addr["housenumber"]}, {addr["postcode"]} {addr["city"]}')
            raise
        
    def isAddr(addr):
        return ('street' in addr) and ('housenumber' in addr) and ('postcode' in addr) and ('city' in addr) and (addr['city'] == 'Bonn')

    for nodeelem in root.findall('node'):
        coords = (float(nodeelem.attrib['lat']), float(nodeelem.attrib['lon']))
        nodes[nodeelem.attrib['id']] = coords
        addr = extractAddr(nodeelem)    
        if isAddr(addr):
            addAddr(addr, [coords])

    for wayelem in root.findall('way'):
        addr = extractAddr(wayelem)    
        if isAddr(addr):
            # Alle nodes zum way finden, und deren Koordinaten zu einer Liste zusammenbauen.
            coords = []
            ids = []
            for nodeelem in wayelem.findall('nd'):
                id = nodeelem.attrib['ref']
                if not id in ids:
                    ids.append(id)
                    coords.append(nodes[id])

            addAddr(addr, coords)

    # Liste der Koordinaten an jeder Addresse mitteln um einen einzelnen Datenpunkt zu erhalten.
    # TODO: Make into a pythonic one-liner :-)
    print('OSM Koordinaten mitteln...')
    for a in addresses.keys():    
        p = (0.0, 0.0)
        n = 0
        for r in addresses[a]:
            n += 1
            p = (p[0] +  r[0], p[1] + r[1])
        p = (p[0] / n, p[1] / n)
        
        addresses[a] = p

    print('OSM speichere Adressen...')
    ad = list(addresses.keys())
    ad.sort()
    with open(f'OSM-Adressen.txt', 'w') as f:
        for a in ad:
            print(a, addresses[a], file = f)

    print('OSM speichere Straßen...')
    sr = list(streetranges.keys())
    sr.sort()
    with open(f'OSM-Strassen.txt', 'w') as f:
        for s in sr:
            print(s, streetranges[s], file = f)
# Ende comment-out-if für OSM-Daten

# Gesamtliste aller Abfuhr-Termine leer initialisieren.
termine = []

# CSV einlesen.
print(f'Öffne "{CSV_FILENAME}"...')
csvfile = open(CSV_FILENAME, newline='', encoding="utf8")
reader = csv.reader(csvfile, delimiter='\t')

# Für alle Zeilen..
for row in reader:

    # Filtern auf Sperrmülltermin.
    if row[COL_TYP] == 'Sperrmüll':
        # Alle Termin-Spalten:
        for termincol in range(COL_TERMIN_00, len(row)):
            terminstr = row[termincol]

            if terminstr:
                try:
                    termindt = datetime.datetime.strptime(terminstr, '%d.%m.%Y')
                    
                    # Termin in die Gesamtliste aller Termine eintragen.
                    if not termindt in termine:
              
                        print(f'Neuer Sperrmülltermin gefunden: {terminstr}')
                        termine.append(termindt)

                except ValueError as err:
                    # An dieser Stelle steht kein Datum. Datenqualität ist Glückssache.
                    # Wir ignorieren das.
                    pass

# Liste aller Abfuhrtermine als Textdatei speichern.
if not os.path.exists(YEAR):
    os.makedirs(YEAR)            

termine.sort()
with open(YEAR + '/Termine.txt', 'w') as f:
    for termin in termine:
        print(termin, file = f)

print('')

# Für jeden gefundenen Abfuhrtermin:
for maptermin in termine:

    # Datum als String in dem Format formatieren in dem es in der CSV-Datei steht.
    mapterminstr = maptermin.strftime('%d.%m.%Y')
    print(f'termin={maptermin} -> maptermin={mapterminstr}: ', end='')

    # Ausgabe-Dateinamen mit dem selektieren Termindatum dekorieren.  
    foldername = YEAR + '\\' + maptermin.strftime('%Y-%m-%d')
    
    if os.path.isdir(foldername):
        # Wenn es den Ordner schon gibt, glauben wir, dass der Termin schon verarbeitet wurde.
        print('Already processed')
    elif False: # maptermin < datetime.datetime.today():
        # Uns interessiert hier nur die Zukunft.
        print('In the past')
    else:
        print('Processing')
        
        # Gesamtliste aller Adresen und Koordinaten leer initialisieren.
        adressen = []
        coordinates = []

        # CSV-Datei öffnen und lesen.
        csvfile = open(CSV_FILENAME, newline='', encoding="utf8")
        reader = csv.reader(csvfile, delimiter='\t')

        # Für alle Zeilen..
        for row in reader:

            # Filtern auf Sperrmülltermin.
            if row[COL_TYP] == 'Sperrmüll':

                # Alle Termine
                for termincol in range(COL_TERMIN_00, len(row)):
                    terminstr = row[termincol]
                    
                    # Ist dies ein Eintrag zum aktuellen Termin?
                    if terminstr == mapterminstr:
                        
                        # Schreibweise der Strasse zwischen der Stadt Bonn und OSM anpassen..
                        strasse = row[COL_STRASSE]
                        if not strasse in streetranges:
                            strasse = strasse.replace('str.', 'straße')
                            strasse = strasse.replace('Str.', 'Straße')

                        if not strasse in streetranges:
                            print(f'"{row[COL_STRASSE]}" nicht in OSM Straßenverzeichnis gefunden')
                        else:     
                            # Hausnummernbereiche sind von der Stadt Bonn separat als ungerade und gerade
                            # Seite spezifiziert. Außerdem werden Platzhalter wie 0 und 9998/9999 verwendet.
                            # Da wir die OSM-Daten kennen können wir die Bereiche effizienter ausdrücken
                            # um weniger Geocoder-Misses zu generieren.
                                               
                            # Startwert für die Hausnummer ermitteln.
                            hnr_ab = streetranges[strasse][0]
                            if row[COL_HAUSNUMMER_UNGERADE_AB]:
                                if row[COL_HAUSNUMMER_GERADE_AB]:
                                    # Ungerade und gerade beide gegeben.
                                    hnr_ab = max(hnr_ab, min(int(row[COL_HAUSNUMMER_UNGERADE_AB]), int(row[COL_HAUSNUMMER_GERADE_AB])))
                                else:
                                    # Nur ungerade gegeben:
                                    hnr_ab = max(hnr_ab, int(row[COL_HAUSNUMMER_UNGERADE_AB]))
                            else:
                                if row[COL_HAUSNUMMER_GERADE_AB]:
                                    # Nur gerade gegeben.
                                    hnr_ab = max(hnr_ab, int(row[COL_HAUSNUMMER_GERADE_AB]))
                                
                            # Endwert für die Hausnummer ermitteln.
                            hnr_bis = streetranges[strasse][1]
                            if row[COL_HAUSNUMMER_UNGERADE_BIS]:
                                if row[COL_HAUSNUMMER_GERADE_BIS]:
                                    # Ungerade und gerade beide gegeben.
                                    hnr_bis = min(hnr_bis, max(int(row[COL_HAUSNUMMER_UNGERADE_BIS]), int(row[COL_HAUSNUMMER_GERADE_BIS])))
                                else:
                                    # Nur ungerade gegeben:
                                    hnr_bis = min(hnr_bis, int(row[COL_HAUSNUMMER_UNGERADE_BIS]))
                            else:
                                if row[COL_HAUSNUMMER_GERADE_BIS]:
                                    # Nur gerade gegeben.
                                    hnr_bis = min(hnr_bis, int(row[COL_HAUSNUMMER_GERADE_BIS]))
                            
                            addr = strasse + ' '

                            if (hnr_ab == hnr_bis):
                                # Nur eine Hausnummer
                                addr += str(hnr_ab) + ' '
                            else:
                                # Hausnummernbereich
                                addr += str(hnr_ab) + '-' + str(hnr_bis) + ' '

                            if row[COL_PLZ]:
                                addr +=   row[COL_PLZ] + ' '
                            
                            addr += row[COL_ORT]

                            # Wenn wir eine Hausnummer und eine neue Strasse+Hausnummer/n haben, dann diesen 
                            # Adressbereich notieren und die Hausnummern im Bereich geokodieren. 
                            if not addr in adressen:
                                print(addr)
                                adressen.append(addr) 
        
                                for hnr in range(hnr_ab, hnr_bis+1):
                                    addr = strasse + ' ' + str(hnr) +', ' + row[COL_PLZ] + ' ' + row[COL_ORT]
                                    print('    ' + addr, end = '')             
                                
                                    if not addr in addresses:
                                        print(f' -> not found')
                                    else:
                                        location = addresses[addr]
                                                            
                                        coords = (addr, location[0], location[1])
                                        print(' ->', location)

                                        if not coords in coordinates:
                                            coordinates.append(coords)

        print(f'Karte anlegen...')

        # Ordner für den Tag anlegen
        if not os.path.exists(foldername):
            os.makedirs(foldername)            

        # Folium-Karte rund um Bonn initialisieren.
        map = folium.Map(
            location = (50.73743, 7.0982068),
            zoom_start = 11
        )

        # Kartentitel konfigurieren.
        title = '<h3>Sperrmüllgebiet Bonn ' + mapterminstr + '</h3>'   
        map.get_root().html.add_child(folium.Element(title))

        # An jede Adresse die zum selektieren Termin eine Abfuhr hat 
        # einen Punkt in die Karte malen.
        for coords in coordinates:
            folium.Circle(
                radius = 2,
                location = (coords[1], coords[2]),
                color = "crimson",
                fill = True,
                opacity = 1,
                fill_opacity = 1,
                tooltip = coords[0]
                # popup = coords[0]
            ).add_to(map)

        # Karte als Datei speichern.
        map.save(f'{foldername}\\Karte.html')

        # Liste aller Koordinaten als Datei speichern.
        coordinates.sort()
        with open(f'{foldername}\\Koordinaten.txt', 'w') as f:
            for coords in coordinates:
                print(str(coords), file = f)
                    
        # Liste aller Adressen (Straße und Hausnummernbereich) als Datei speichern.
        adressen.sort()
        with open(f'{foldername}\\Adressen.txt', 'w') as f:            
            for adresse in adressen:
                print(adresse, file = f)

        # Liste der Termine auch zwischendurch speichern.
        saveTermine()
        
# Vollständige Liste der Termine speichern. 
saveTermine()