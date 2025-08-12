# Liste des grandes villes du Grand Est avec coordonnées centre-ville
GRAND_EST_CITIES = [
    {"ville": "Strasbourg", "lat": 48.5734, "lon": 7.7521},
    {"ville": "Metz", "lat": 49.1193, "lon": 6.1757},
    {"ville": "Nancy", "lat": 48.6921, "lon": 6.1844},
    {"ville": "Reims", "lat": 49.2583, "lon": 4.0317},
    {"ville": "Mulhouse", "lat": 47.7508, "lon": 7.3359},
    {"ville": "Colmar", "lat": 48.0794, "lon": 7.3585},
    {"ville": "Charleville-Mézières", "lat": 49.7739, "lon": 4.7208},
    {"ville": "Troyes", "lat": 48.2973, "lon": 4.0744},
    {"ville": "Épinal", "lat": 48.1724, "lon": 6.4496},
    {"ville": "Châlons-en-Champagne", "lat": 48.9562, "lon": 4.3674},
]

def get_weather_data_cities():
    session = requests.Session()
    session.headers.update({"User-Agent": "meteo-grid-app"})

    results = []
    for city in GRAND_EST_CITIES:
        params = {
            'latitude': city['lat'], 'longitude': city['lon'],
            'hourly': 'temperature_2m,precipitation',
            'models': 'icon_eu,gfs_global',
            'forecast_days': 7,
            'timezone': 'Europe/Paris'
        }
        try:
            r = session.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
            r.raise_for_status()
            hourly = r.json().get('hourly', {})
            time_idx = hourly.get('time')
            if not time_idx:
                continue

            def pick_var(base):
                for k in (f"{base}_icon_eu", f"{base}_gfs_global", base):
                    if k in hourly:
                        return hourly[k]
                return None

            temps = pick_var('temperature_2m')
            precs = pick_var('precipitation')
            if temps is None or precs is None:
                continue

            df = pd.DataFrame({
                'datetime': pd.to_datetime(time_idx),
                'temp': temps,
                'precip': precs,
                'latitude': city['lat'],
                'longitude': city['lon'],
                'ville': city['ville']
            })
            df['date'] = df['datetime'].dt.date
            results.append(df)
        except:
            continue

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)
