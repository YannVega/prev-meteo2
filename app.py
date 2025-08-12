import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import requests
from datetime import date
import time

@st.cache_data(show_spinner="Chargement des données météo...")
def get_weather_data():
    lat_grid = np.arange(47.9, 49.5, 0.225)
    lon_grid = np.arange(4.5, 7.3, 0.325)
    grid_points = [(round(lat, 4), round(lon, 4)) for lat in lat_grid for lon in lon_grid]

    commune_cache = {}
    results = []
    session = requests.Session()
    session.headers.update({"User-Agent": "meteo-grid-app - contact@example.com"})

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
            postcode = address.get('postcode', '') or ''
            dept = postcode[:2] if postcode else None
            commune_cache[key] = {"commune": commune, "dept": dept}
            # pause courte pour ne pas spammer Nominatim
            time.sleep(0.4)
            return commune_cache[key]
        except Exception:
            commune_cache[key] = {"commune": None, "dept": None}
            return commune_cache[key]

    for lat, lon in grid_points:
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'temperature_2m,precipitation',
            'models': 'icon_eu,gfs_global',
            'forecast_days': 7,
            'timezone': 'Europe/Paris'
        }
        try:
            r = session.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            hourly = data.get('hourly', {})
            time_idx = hourly.get('time')
            if not time_idx:
                continue

            # Choisir la meilleure variable disponible (priorité aux suffixes modèle)
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
                'precip': precs
            })
            df['latitude'] = lat
            df['longitude'] = lon

            info = get_commune_with_dept(lat, lon)
            df['commune'] = info['commune']
            df['dept'] = info['dept']

            results.append(df)
        except Exception:
            continue

    if not results:
        return pd.DataFrame(columns=['datetime', 'temp', 'precip', 'latitude', 'longitude', 'commune', 'dept'])

    df_all = pd.concat(results, ignore_index=True)
    # ne garder que les départements d'intérêt
    df_all = df_all[df_all['dept'].isin(['54', '55', '88'])].copy()
    df_all['date'] = df_all['datetime'].dt.date

    return df_all

# App Streamlit
st.set_page_config(layout="wide")
st.title("Prévisions météo - Popup détaillé par commune")

df = get_weather_data()

if df.empty:
    st.error("Pas de données récupérées (vérifiez la connexion ou le filtrage par département).")
    st.stop()

# Sélecteurs de date
dates = sorted(df['date'].dropna().unique())
min_d, max_d = dates[0], dates[-1]

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date de début", min_value=min_d, max_value=max_d, value=min_d)
with col2:
    end_date = st.date_input("Date de fin", min_value=min_d, max_value=max_d, value=max_d)

if start_date > end_date:
    st.warning("⚠️ La date de début est postérieure à la date de fin.")
    st.stop()

df_period = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
if df_period.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

days = (end_date - start_date).days + 1

# === Fonctions pour popup détaillé ===
def make_popup_single(commune, temp_mean, temp_min, temp_max, precip_sum):
    return (
        f"<b>{commune}</b><br>"
        f"Température moyenne : {temp_mean:.2f} °C<br>"
        f"Température minimale : {temp_min:.2f} °C<br>"
        f"Température maximale : {temp_max:.2f} °C<br>"
        f"Précipitations totales : {precip_sum:.2f} mm"
    )

def make_popup_table(commune, temp_min_df, temp_max_df, precip_df, dates):
    rows = []
    header = "<tr><th>Variable</th>" + "".join(f"<th>{d.strftime('%Y-%m-%d')}</th>" for d in dates) + "</tr>"
    rows.append(header)

    def make_row(label, df):
        cells = []
        for d in dates:
            try:
                val = df.loc[commune, d]
                cell = "NA" if pd.isna(val) else f"{val:.2f}"
            except Exception:
                cell = "NA"
            cells.append(f"<td style='padding:4px'>{cell}</td>")
        return f"<tr><td style='padding:4px'>{label}</td>" + "".join(cells) + "</tr>"

    rows.append(make_row("Température minimale (°C)", temp_min_df))
    rows.append(make_row("Température maximale (°C)", temp_max_df))
    rows.append(make_row("Précipitations (mm)", precip_df))

    table_html = "<table border='1' style='border-collapse: collapse; font-size: 11px;'>" + "".join(rows) + "</table>"
    return f"<b>{commune}</b><br>{table_html}"

# === Création de la carte ===
m = folium.Map(location=[48.5, 6.3], zoom_start=8, tiles="CartoDB positron")

if days == 1:
    agg = df_period.groupby('commune').agg(
        temp_mean=('temp', 'mean'),
        temp_min=('temp', 'min'),
        temp_max=('temp', 'max'),
        precip_sum=('precip', 'sum'),
        latitude=('latitude', 'mean'),
        longitude=('longitude', 'mean')
    ).reset_index()

    for _, row in agg.iterrows():
        popup_html = make_popup_single(row['commune'], row['temp_mean'], row['temp_min'], row['temp_max'], row['precip_sum'])
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=450),
            icon=folium.Icon(color='blue')
        ).add_to(m)

else:
    daily = df_period.groupby(['commune', 'date', 'latitude', 'longitude']).agg(
        temp_mean=('temp', 'mean'),
        temp_min=('temp', 'min'),
        temp_max=('temp', 'max'),
        precip_sum=('precip', 'sum')
    ).reset_index()

    dates_list = sorted(df_period['date'].unique())
    temp_min_df = daily.pivot(index='commune', columns='date', values='temp_min')
    temp_max_df = daily.pivot(index='commune', columns='date', values='temp_max')
    precip_df = daily.pivot(index='commune', columns='date', values='precip_sum')

    loc = daily.groupby('commune')[['latitude', 'longitude']].mean()

    for commune in temp_min_df.index:
        lat = loc.loc[commune, 'latitude']
        lon = loc.loc[commune, 'longitude']
        popup_html = make_popup_table(commune, temp_min_df, temp_max_df, precip_df, dates_list)
        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_html, max_width=800),
            icon=folium.Icon(color='green')
        ).add_to(m)

# Affichage carte
st_folium(m, width=1200, height=700)
