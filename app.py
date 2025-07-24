import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import numpy as np

# 1. Récupération + géocodage des données (mis en cache)
@st.cache_data(show_spinner="Chargement des données...")
def get_weather_data():
    lat_grid = np.arange(47.9, 49.5, 0.225)
    lon_grid = np.arange(4.5, 7.3, 0.325)
    grid_points = [(round(lat, 4), round(lon, 4)) for lat in lat_grid for lon in lon_grid]

    commune_cache = {}
    results = []

    def get_commune_with_dept(lat, lon):
        key = (round(lat, 3), round(lon, 3))
        if key in commune_cache:
            return commune_cache[key]

        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': lat, 'lon': lon,
            'format': 'jsonv2', 'zoom': 10,
            'addressdetails': 1
        }

        try:
            r = requests.get(url, params=params, headers={"User-Agent": "geo-app"})
            if r.status_code == 200:
                address = r.json().get('address', {})
                commune = (
                    address.get('city') or address.get('town') or
                    address.get('village') or address.get('municipality')
                )
                dept = address.get('postcode', '')[:2]
                commune_cache[key] = {"commune": commune, "dept": dept}
                return commune_cache[key]
        except:
            pass
        return {"commune": None, "dept": None}

    for lat, lon in grid_points:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,relative_humidity_2m,precipitation"
            "&models=icon_eu,gfs_global"
            "&forecast_days=7&timezone=Europe%2FParis"
        )
        r = requests.get(url)
        if r.status_code != 200:
            continue
        data = r.json()

        try:
            df = pd.DataFrame({
                'datetime': pd.to_datetime(data['hourly']['time']),
                'temp_ICON': data['hourly']['temperature_2m_icon_eu'],
                'hygro_ICON': data['hourly']['relative_humidity_2m_icon_eu'],
                'pluvio_GFS': data['hourly']['precipitation_gfs_global'],
            })
            df['latitude'] = lat
            df['longitude'] = lon
            info = get_commune_with_dept(lat, lon)
            df['commune'] = info['commune']
            df['dept'] = info['dept']
            results.append(df)
        except:
            continue

    if results:
        df_all = pd.concat(results, ignore_index=True)
        # Filtrer uniquement départements 54, 55, 88
        return df_all[df_all["dept"].isin(["54", "55", "88"])].copy()
    else:
        return pd.DataFrame()

# --- Streamlit UI ---

st.title("Prévisions météo (54, 55, 88)")
st.markdown("Carte interactive avec données à J+7")

# Chargement des données
df = get_weather_data()

if df.empty:
    st.warning("Aucune donnée météo disponible.")
    st.stop()

# Convertir datetime en date pour le filtre
df['date'] = df['datetime'].dt.date
dates = df['date'].unique()
start_date = st.date_input("Date de début", value=dates.min(), min_value=dates.min(), max_value=dates.max())
end_date = st.date_input("Date de fin", value=dates.max(), min_value=dates.min(), max_value=dates.max())

if start_date > end_date:
    st.error("La date de début doit être antérieure à la date de fin.")
    st.stop()

# Filtrer le dataframe selon les dates choisies
df_filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

# Création carte Folium
m = folium.Map(location=[48.5, 6.3], zoom_start=8, tiles="CartoDB positron")

for commune in df_filtered["commune"].dropna().unique():
    sub = df_filtered[df_filtered["commune"] == commune]
    lat = sub["latitude"].iloc[0]
    lon = sub["longitude"].iloc[0]

    popup_html = (
        f"<b>{commune}</b><br>"
        f"Température moyenne : {sub['temp_ICON'].mean():.1f} °C<br>"
        f"Humidité moyenne : {sub['hygro_ICON'].mean():.1f} %<br>"
        f"Précipitations totales : {sub['pluvio_GFS'].sum():.1f} mm"
    )
    folium.Marker([lat, lon], popup=popup_html, icon=folium.Icon(color="blue")).add_to(m)

st_folium(m, width=700, height=500)
