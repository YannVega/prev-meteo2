import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import requests

@st.cache_data(show_spinner="Chargement des données météo...")
def get_weather_data():
    lat_grid = np.arange(47.9, 49.5, 0.225)
    lon_grid = np.arange(4.5, 7.3, 0.325)
    grid_points = [(round(lat, 4), round(lon, 4)) for lat in lat_grid for lon in lon_grid]

    session = requests.Session()
    session.headers.update({"User-Agent": "meteo-grid-app"})

    results = []
    for lat, lon in grid_points:
        params = {
            'latitude': lat, 'longitude': lon,
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
                'latitude': lat,
                'longitude': lon
            })
            results.append(df)
        except:
            continue

    if not results:
        return pd.DataFrame()

    df_all = pd.concat(results, ignore_index=True)
    df_all['date'] = df_all['datetime'].dt.date
    return df_all

# -------------------
# Streamlit app
# -------------------
st.set_page_config(layout="wide")
st.title("Prévisions météo - Min / Max / Moyenne + Pluviométrie journalière (coords uniquement)")

df = get_weather_data()
if df.empty:
    st.error("Pas de données récupérées.")
    st.stop()

dates = sorted(df['date'].unique())
min_d, max_d = dates[0], dates[-1]

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date début", min_d, min_value=min_d, max_value=max_d)
with col2:
    end_date = st.date_input("Date fin", max_d, min_value=min_d, max_value=max_d)

if start_date > end_date:
    st.warning("Date de début après date de fin.")
    st.stop()

df_period = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
if df_period.empty:
    st.warning("Aucune donnée pour cette période.")
    st.stop()

days = (end_date - start_date).days + 1

# Agrégations journalières
daily = df_period.groupby(['latitude', 'longitude', 'date']).agg(
    temp_mean=('temp', 'mean'),
    temp_min=('temp', 'min'),
    temp_max=('temp', 'max'),
    precip_sum=('precip', 'sum')
).reset_index()

def make_popup_single(row):
    return (
        f"Coordonnées : ({row['latitude']:.4f}, {row['longitude']:.4f})<br>"
        f"Temp. moyenne : {row['temp_mean']:.2f} °C<br>"
        f"Temp. min : {row['temp_min']:.2f} °C<br>"
        f"Temp. max : {row['temp_max']:.2f} °C<br>"
        f"Pluie totale : {row['precip_sum']:.2f} mm"
    )

# Carte
m = folium.Map(location=[48.5, 6.3], zoom_start=8, tiles="CartoDB positron")

if days == 1:
    agg = daily.groupby(['latitude', 'longitude']).mean(numeric_only=True).reset_index()
    for _, row in agg.iterrows():
        folium.CircleMarker(
            [row['latitude'], row['longitude']],
            radius=4,
            color='blue',
            fill=True,
            fill_color='blue',
            popup=folium.Popup(make_popup_single(row), max_width=350)
        ).add_to(m)
else:
    for (lat, lon), group in daily.groupby(['latitude', 'longitude']):
        popup_html = f"<b>Coordonnées : ({lat:.4f}, {lon:.4f})</b><br>"
        popup_html += "<table border='1' style='border-collapse:collapse;font-size:11px'>"
        popup_html += "<tr><th>Date</th><th>Min °C</th><th>Max °C</th><th>Moy °C</th><th>Pluie mm</th></tr>"
        for _, r in group.iterrows():
            popup_html += f"<tr><td>{r['date']}</td><td>{r['temp_min']:.1f}</td><td>{r['temp_max']:.1f}</td><td>{r['temp_mean']:.1f}</td><td>{r['precip_sum']:.1f}</td></tr>"
        popup_html += "</table>"
        folium.CircleMarker(
            [lat, lon],
            radius=4,
            color='green',
            fill=True,
            fill_color='green',
            popup=folium.Popup(popup_html, max_width=800)
        ).add_to(m)

st_folium(m, width=1200, height=700)
