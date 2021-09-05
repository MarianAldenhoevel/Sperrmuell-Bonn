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
'''

import os
import datetime
import json
import csv
import geopy
import folium
import ratelimit
import backoff

# Nominatim-basierten Geocoder vorbereiten.
geolocator = geopy.geocoders.Nominatim(user_agent="Sperrmülltermine Bonn")

# Handler for backoff on the geocode service
def backoff_handler(details):
    print(f'        Backing off {details["wait"]:0.1f} seconds after {details["tries"]} tries')

# Nominatim-Aufruffrequenz beschränken. Höchstens ein Aufruf pro Sekunde.
# Und verzögern wenn dies überschritten wird statt einen Fehler auszulösen.
@ratelimit.sleep_and_retry
@ratelimit.limits(1, 1.1)
@backoff.on_exception(backoff.expo,
                      geopy.exc.GeocoderServiceError,
                      on_backoff = backoff_handler,
                      max_time = 60*60 + 60) # One hour and some
def rate_limited_geocode(addr):
    return geolocator.geocode(addr, addressdetails = True)

# Einstellungen ab hier:

# Dateiname des aktuellen CSV-Downloads:
CSV_FILENAME = 'ABFUHRTERMINE2021.csv'

# Spaltenindizes im CSV:
COL_TYP = 17        # Spalte in der der Abfuhrtyp steht. Wir suchen "Sperrmüll"
COL_TERMIN_00 = 54  # Spalte in der der erste Abfuhrtermin steht, Annahme: Der Rest nach rechts sind weitere Termine 

COL_STRASSE = 31    
COL_ORT = 32
COL_PLZ = 34
COL_HAUSNUMMER_GERADE_AB = 35
COL_HAUSNUMMER_GERADE_BIS = COL_HAUSNUMMER_GERADE_AB + 1

COL_HAUSNUMMER_UNGERADE_AB = 37
COL_HAUSNUMMER_UNGERADE_BIS = COL_HAUSNUMMER_UNGERADE_AB + 1

# Die Daten sagen 1-9999 bzw 2-9998 wenn die ganze Straße gemeint ist. Um nicht alle vergeblich
# abzufragen hier eine willkürlich gewählte Obergrenze die auf "ab" aufgeschlagen wird.
MAX_HAUSNUMMER_FOR_GEOLOCATION = 100

# Gesamtliste aller Termine leer initialisieren.
termine = []

# CSV einlesen.
csvfile = open(CSV_FILENAME, newline='')
reader = csv.reader(csvfile, delimiter=';')

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
termine.sort()
with open('Termine.txt', 'w') as f:
    for termin in termine:
        print(termin, file = f)

print('')

# Für jeden gefundenen Abfuhrtermin:
for maptermin in termine:

    # Datum als String in dem Format formatieren in dem es in der CSV-Datei steht.
    mapterminstr = maptermin.strftime('%d.%m.%Y')
    print(f'{maptermin} -> {mapterminstr}: ', end='')

    # Ausgabe-Dateinamen mit dem selektieren Termindatum dekorieren.  
    foldername = maptermin.strftime('%Y-%m-%d')
    
    if os.path.isdir(foldername):
        # Wenn es den Ordner schon gibt, glauben wir, dass der Termin schon verarbeitet wurde.
        print('Already processed')
    elif maptermin < datetime.datetime.today():
        # Uns interessiert hier nur die Zukunft
        print('In the past')
    else:
        print('Processing')
        
        # Gesamtliste aller Adresen und Koordinaten leer initialisieren.
        adressen = []
        coordinates = []

        # CSV-Datei öffnen und lesen.
        csvfile = open(CSV_FILENAME, newline='')
        reader = csv.reader(csvfile, delimiter=';')

        # Für alle Zeilen..
        for row in reader:

            # Filtern auf Sperrmülltermin.
            if row[COL_TYP] == 'Sperrmüll':

                # Alle Termine
                for termincol in range(COL_TERMIN_00, len(row)):
                    terminstr = row[termincol]
                    
                    # Ist dies ein Eintrag zum aktuellen Termin?
                    if terminstr == mapterminstr:
                        
                        # Hausnummern für die Darstellung zusammenbauen.
                        if row[COL_HAUSNUMMER_UNGERADE_AB] == row[COL_HAUSNUMMER_UNGERADE_BIS]:
                            hnr = row[COL_HAUSNUMMER_UNGERADE_AB]
                        else:
                            hnr = row[COL_HAUSNUMMER_UNGERADE_AB] + '-' + row[COL_HAUSNUMMER_UNGERADE_BIS]
                        
                        if row[COL_HAUSNUMMER_GERADE_AB] == row[COL_HAUSNUMMER_GERADE_BIS]:
                            hnr += ' ' + row[COL_HAUSNUMMER_GERADE_AB]
                        else:
                            hnr += ' ' + row[COL_HAUSNUMMER_GERADE_AB] + '-' + row[COL_HAUSNUMMER_GERADE_BIS]

                        addr = row[COL_STRASSE] + ' ' + hnr +', '
                        
                        if row[COL_PLZ]:
                            addr +=   row[COL_PLZ] + ' '
                        
                        addr += row[COL_ORT]
                        
                        # Wenn wir eine Hausnummer und eine neue Strasse+Hausnummer/n haben, dann diesen 
                        # Adressbereich notieren und die Hausnummern im Bereich geokodieren. 
                        if hnr.strip() and (not addr in adressen):
                            print(addr)
                            adressen.append(addr) 
       
                            def processrange(von, bis):                                

                                # Suche begrenzen. Nur wenn das Geocoding erfolgreich ist, erweitern wir
                                # den Suchbereich bis maximal zur bis-Hausnummer.
                                maxh = von + MAX_HAUSNUMMER_FOR_GEOLOCATION

                                h = von
                                while h <= maxh:
                                    addr = row[COL_STRASSE] + ' ' + str(h) +', ' + row[COL_PLZ] + ' ' + row[COL_ORT]
                                    print('    ' + addr)             
                                    
                                    location = rate_limited_geocode(addr)
                                    if (not location) or (not 'house_number' in location.raw['address']):
                                        print('        No result from geocoder')
                                    else:       
                                        coords = (str(location), location.latitude, location.longitude)
                                        print('        ' + str(location))
                                        print('        ' + str(coords))

                                        global coordinates                                            
                                        if not coords in coordinates:
                                            # Wir haben neue Koordinaten. In dem Fall sind wir bereit von dieser
                                            # Hausnummer aus weiter zu suchen. Aber nie weiter als in den Daten
                                            # spezifiziert. 
                                            maxh = min(bis, h + MAX_HAUSNUMMER_FOR_GEOLOCATION)
                                            
                                            coordinates.append(coords)

                                    h += 2 # Wir sind auf der geraden oder ungeraden Straßenseite. Also in Schritten von 2.           
                                            
                            if row[COL_HAUSNUMMER_UNGERADE_AB] and row[COL_HAUSNUMMER_UNGERADE_BIS]:
                                processrange(int(row[COL_HAUSNUMMER_UNGERADE_AB]), int(row[COL_HAUSNUMMER_UNGERADE_BIS]))

                            if row[COL_HAUSNUMMER_GERADE_AB] and row[COL_HAUSNUMMER_GERADE_BIS]:
                                processrange(int(row[COL_HAUSNUMMER_GERADE_AB]), int(row[COL_HAUSNUMMER_GERADE_BIS]))

        # Ordner für den Tag anlegen
        if not os.path.exists(foldername):
            os.mkdir(foldername)            

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

# Liste aller Abfuhrtermine als HTML-Fragment mit Links auf die Karte und andere Ausgaben speichern.
with open('Termine.html', 'w') as f:
    todaystr = datetime.datetime.today().strftime('%d.%m.')
    yearstr = datetime.datetime.today().strftime('%Y')
    print(f'<h1>Sperrmülltermine Bonn {yearstr} ab {todaystr}</h1>', file = f)
    print(f'<ul>', file = f)

    for termin in termine:
        foldername = termin.strftime('%Y-%m-%d')
        
        if os.path.exists(foldername): # Nur erfolgreich verarbeitete
            terminstr = termin.strftime('%d.%m.%Y')
            print(f'  <li>', file = f)
            print(f'    <span>{terminstr}: </span>', file = f)
            print(f'    <a href="{foldername}/Karte.html">Karte</a> - ', file = f)
            print(f'    <a href="{foldername}/Adressen.txt">Adressen</a> - ', file = f)
            print(f'    <a href="{foldername}/Koordinaten.txt">Koordinaten</a>', file = f)          
            print(f'  </li>', file = f)

    print(f'</ul>', file = f)
