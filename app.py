import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import requests
import os
import time

# ==========================
# PARAMÈTRES
# ==========================
DEPTS = ["54", "55", "88"]
CACHE_GEOCODE = "communes_cache.csv"

@st.cache_data(show_spinner="Chargement des données météo...")
def get_weather_data():
    # Grille régulière
    lat_grid = np.arange(47.9, 49.5, 0.225)
    lon_grid = np.arange(4.5, 7.3, 0.325)
    grid_points = [(round(lat, 4), round(lon, 4)) for lat in lat_grid for lon in lon_grid]

    # Charger cache géocodage si dispo
    commune_cache = {}
    if os.path.exists(CACHE_GEOCODE):
        commune_cache = pd.read_csv(CACHE_GEOCODE).set_index(['lat', 'lon']).to_dict(orient="index")

    session = requests.Session()
    session.headers.update({"User-Agent": "meteo-grid-app"})

    def get_commune_with_dept(lat, lon):
        key = (round(lat, 3), round(lon, 3))
        if key in commune_cache:
            return commune_cache[key]
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {'lat': lat, 'lon': lon, 'format': 'jsonv2', 'zoom': 10, 'addressdetails': 1}
        try:
            r = session.get(url, params=params, timeout=10)
            r.raise_for_status()
            address = r.json().get('address', {})
            commune = address.get('city') or address.get('town') or address.get('village') or address.get('municipality')
            dept = (address.get('postcode') or '')[:2]
            commune_cache[key] = {"commune": commune, "dept": dept}
            return commune_cache[key]
        except:
            commune_cache[key] = {"commune": None, "dept": None}
            return commune_cache[key]

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
            info = get_commune_with_dept(lat, lon)
            df['commune'] = info['commune']
            df['dept'] = info['dept']
            results.append(df)
        except:
            continue

    # Sauvegarder le cache géocodage
    pd.DataFrame(
        [{"lat": k[0], "lon": k[1], **v} for k, v in commune_cache.items()]
    ).to_csv(CACHE_GEOCODE, index=False)

    if not results:
        return pd.DataFrame()

    df_all = pd.concat(results, ignore_index=True)
    df_all = df_all[df_all['dept'].isin(DEPTS)].copy()
    df_all['date'] = df_all['datetime'].dt.date
    return df_all

# -------------------
# Streamlit app
# -------------------
st.set_page_config(layout="wide")
st.title("Prévisions météo - Min / Max / Moyenne + Pluviométrie journalière")

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
daily = df_period.groupby(['commune', 'date', 'latitude', 'longitude']).agg(
    temp_mean=('temp', 'mean'),
    temp_min=('temp', 'min'),
    temp_max=('temp', 'max'),
    precip_sum=('precip', 'sum')
).reset_index()

# Fonctions popups
def make_popup_single(row):
    return (
        f"<b>{row['commune']}</b><br>"
        f"Temp. moyenne : {row['temp_mean']:.2f} °C<br>"
        f"Temp. min : {row['temp_min']:.2f} °C<br>"
        f"Temp. max : {row['temp_max']:.2f} °C<br>"
        f"Pluie totale : {row['precip_sum']:.2f} mm"
    )

def make_popup_table(commune, tmn, tmx, tmd, pcp, dates):
    header = "<tr><th>Date</th><th>Min °C</th><th>Max °C</th><th>Moy °C</th><th>Pluie mm</th></tr>"
    rows = []
    for d in dates:
        try:
            rows.append(f"<tr><td>{d}</td>"
                        f"<td>{tmn.loc[commune, d]:.1f}</td>"
                        f"<td>{tmx.loc[commune, d]:.1f}</td>"
                        f"<td>{tmd.loc[commune, d]:.1f}</td>"
                        f"<td>{pcp.loc[commune, d]:.1f}</td></tr>")
        except:
            pass
    return f"<b>{commune}</b><br><table border='1' style='border-collapse:collapse;font-size:11px'>{header}{''.join(rows)}</table>"

# Carte
m = folium.Map(location=[48.5, 6.3], zoom_start=8, tiles="CartoDB positron")

if days == 1:
    agg = daily.groupby('commune').agg({
        'temp_mean': 'mean', 'temp_min': 'mean', 'temp_max': 'mean', 'precip_sum': 'mean',
        'latitude': 'mean', 'longitude': 'mean'
    }).reset_index()
    for _, row in agg.iterrows():
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=folium.Popup(make_popup_single(row), max_width=350),
            icon=folium.Icon(color='blue')
        ).add_to(m)
else:
    tmn = daily.pivot(index='commune', columns='date', values='temp_min')
    tmx = daily.pivot(index='commune', columns='date', values='temp_max')
    tmd = daily.pivot(index='commune', columns='date', values='temp_mean')
    pcp = daily.pivot(index='commune', columns='date', values='precip_sum')
    loc = daily.groupby('commune')[['latitude', 'longitude']].mean()

    for commune in tmn.index:
        folium.Marker(
            [loc.loc[commune, 'latitude'], loc.loc[commune, 'longitude']],
            popup=folium.Popup(make_popup_table(commune, tmn, tmx, tmd, pcp, sorted(df_period['date'].unique())), max_width=800),
            icon=folium.Icon(color='green')
        ).add_to(m)

st_folium(m, width=1200, height=700)
