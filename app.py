# meteo_lorraine_villes.py

import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

# Liste des villes > 15k hab. en Lorraine
CITIES = [
    {"name": "Nancy", "lat": 48.6921, "lon": 6.1844},
    {"name": "Vandoeuvre-lès-Nancy", "lat": 48.6833, "lon": 6.1528},
    {"name": "Lunéville", "lat": 48.6000, "lon": 6.3850},
    {"name": "Toul", "lat": 48.6833, "lon": 5.9},
    {"name": "Metz", "lat": 49.1193, "lon": 6.1757},
    {"name": "Thionville", "lat": 49.3566, "lon": 6.1689},
    {"name": "Montigny-lès-Metz", "lat": 49.1167, "lon": 6.1500},
    {"name": "Forbach", "lat": 49.1975, "lon": 6.9002},
    {"name": "Sarreguemines", "lat": 49.1125, "lon": 7.3578},
    {"name": "Yutz", "lat": 49.3575, "lon": 6.1778},
    {"name": "Hayange", "lat": 49.3517, "lon": 6.1350},
    {"name": "Épinal", "lat": 48.1741, "lon": 6.4496},
    {"name": "Saint-Dié-des-Vosges", "lat": 48.2910, "lon": 6.8990},
    {"name": "Bar-le-Duc", "lat": 48.7833, "lon": 5.1667},
    {"name": "Verdun", "lat": 49.1611, "lon": 5.3839},
    {"name": "Étaules", "lat": 47.2923, "lon": 5.0550},       # Côte-d'Or (21)
    {"name": "Orléans", "lat": 47.9029, "lon": 1.9093},
    {"name": "Grenoble", "lat": 45.1885, "lon": 5.7245},
    {"name": "Dijon", "lat": 47.3220, "lon": 5.0415},
]

@st.cache_data(show_spinner="Chargement des prévisions météo...")
def get_weather_for_city(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum",
        "timezone": "Europe/Paris",
        "forecast_days": 7
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    daily = r.json().get("daily", {})
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["time"]).dt.date
    return df[["date", "temperature_2m_min", "temperature_2m_max", "temperature_2m_mean", "precipitation_sum"]]

st.set_page_config(layout="wide")
st.markdown("### Météo sur 7 jours — Grandes villes de Lorraine")

# Carte centrée sur Lorraine
m = folium.Map(location=[48.8, 6.2], zoom_start=8, tiles="CartoDB positron")

for city in CITIES:
    df_city = get_weather_for_city(city["lat"], city["lon"])
    header = "<tr><th>Date</th><th>Min</th><th>Max</th><th>Moy</th><th>Pluie</th></tr>"
    rows = [
        f"<tr><td>{row.date}</td><td>{row.temperature_2m_min:.1f}</td>"
        f"<td>{row.temperature_2m_max:.1f}</td><td>{row.temperature_2m_mean:.1f}</td>"
        f"<td>{row.precipitation_sum:.1f}</td></tr>"
        for row in df_city.itertuples()
    ]
    table_html = f"<b>{city['name']}</b><br><table border='1' style='border-collapse:collapse;font-size:11px'>{header}{''.join(rows)}</table>"
    folium.Marker([city["lat"], city["lon"]], popup=folium.Popup(table_html, max_width=800),
                  icon=folium.Icon(color="blue")).add_to(m)

st_folium(m, width=1200, height=700)
