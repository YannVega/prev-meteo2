# meteo_lorraine.py

import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

# ==========================
# Liste des villes (ancienne Lorraine)
# ==========================
CITIES = [
    {"name": "Nancy", "lat": 48.6921, "lon": 6.1844},
    {"name": "Metz", "lat": 49.1193, "lon": 6.1757},
    {"name": "Toul", "lat": 48.6833, "lon": 5.9},
    {"name": "Verdun", "lat": 49.159, "lon": 5.385},
    {"name": "Bar-le-Duc", "lat": 48.77, "lon": 5.1614},
    {"name": "Épinal", "lat": 48.174, "lon": 6.449},
    {"name": "Saint-Dié-des-Vosges", "lat": 48.284, "lon": 6.949},
]

# ==========================
# Récupération météo
# ==========================
@st.cache_data(show_spinner="Chargement des prévisions météo...")
def get_weather_for_city(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,temperature_2m_mean",
        "timezone": "Europe/Paris",
        "forecast_days": 7
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()["daily"]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["time"]).dt.date
    return df[["date", "temperature_2m_min", "temperature_2m_max", "temperature_2m_mean", "precipitation_sum"]]

# ==========================
# Interface Streamlit
# ==========================
st.set_page_config(layout="wide")
st.markdown("### Prévisions météo - Grandes villes de Lorraine (7 jours)")

# Carte
m = folium.Map(location=[48.7, 6.3], zoom_start=8, tiles="CartoDB positron")

for city in CITIES:
    df_city = get_weather_for_city(city["lat"], city["lon"])
    
    # Tableau HTML pour popup
    header = "<tr><th>Date</th><th>Min °C</th><th>Max °C</th><th>Moy °C</th><th>Pluie mm</th></tr>"
    rows = [
        f"<tr><td>{row.date}</td>"
        f"<td>{row.temperature_2m_min:.1f}</td>"
        f"<td>{row.temperature_2m_max:.1f}</td>"
        f"<td>{row.temperature_2m_mean:.1f}</td>"
        f"<td>{row.precipitation_sum:.1f}</td></tr>"
        for row in df_city.itertuples()
    ]
    table_html = f"<b>{city['name']}</b><br><table border='1' style='border-collapse:collapse;font-size:11px'>{header}{''.join(rows)}</table>"
    
    folium.Marker(
        [city["lat"], city["lon"]],
        popup=folium.Popup(table_html, max_width=800),
        icon=folium.Icon(color="blue")
    ).add_to(m)

st_folium(m, width=1200, height=700)
