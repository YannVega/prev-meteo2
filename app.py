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
            "&hourly=temperature_2m,precipitation"
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
        df_all = df_all[df_all["dept"].isin(["54", "55", "88"])].copy()
        df_all['date'] = df_all['datetime'].dt.date
        df_all['temp_min'] = df_all.groupby('date')['temp_ICON'].transform('min')
        df_all['temp_max'] = df_all.groupby('date')['temp_ICON'].transform('max')
        return df_all
    else:
        return pd.DataFrame()

# App Streamlit
st.set_page_config(layout="wide")
st.title("Prévisions météo - Popup détaillé par commune")

df = get_weather_data()

if df.empty:
    st.error("Pas de données récupérées.")
    st.stop()

# Sélecteurs de date
dates = df["date"].dropna().unique()
min_d, max_d = min(dates), max(dates)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Date de début", min_value=min_d, max_value=max_d, value=min_d)
with col2:
    end_date = st.date_input("Date de fin", min_value=min_d, max_value=max_d, value=max_d)

if start_date > end_date:
    st.warning("⚠️ La date de début est postérieure à la date de fin.")
    st.stop()

df_period = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
if df_period.empty:
    st.warning("Aucune donnée sur la période sélectionnée.")
    st.stop()

days = (end_date - start_date).days + 1
df_period["date_day"] = df_period["datetime"].dt.date

# === Fonctions pour popup détaillé ===

def make_popup_single(row):
    return (
        f"<b>{row['commune']}</b><br>"
        f"Température moyenne : {row['temp_ICON']:.2f} °C<br>"
        f"Température minimale : {row['temp_min']:.2f} °C<br>"
        f"Température maximale : {row['temp_max']:.2f} °C<br>"
        f"Précipitations totales : {row['pluvio_GFS']:.2f} mm"
    )

def make_popup_table(commune, temp_min_df, temp_max_df, pluvio_df, dates):
    rows = []
    header = "<tr><th>Variable</th>" + "".join(f"<th>{d.strftime('%m-%d')}</th>" for d in dates) + "</tr>"
    rows.append(header)

    def make_row(label, df):
        cells = []
        for d in dates:
            try:
                val = df.loc[commune, d]
                cell = "NA" if pd.isna(val) else f"{val:.2f}"
            except:
                cell = "NA"
            cells.append(f"<td>{cell}</td>")
        return f"<tr><td>{label}</td>" + "".join(cells) + "</tr>"

    rows.append(make_row("Température minimale (°C)", temp_min_df))
    rows.append(make_row("Température maximale (°C)", temp_max_df))
    rows.append(make_row("Précipitations (mm)", pluvio_df))

    table_html = "<table border='1' style='border-collapse: collapse; font-size: 11px;'>" + "".join(rows) + "</table>"
    return f"<b>{commune}</b><br>{{table_html}}"

# === Création de la carte ===

m = folium.Map(location=[48.5, 6.3], zoom_start=8, tiles="CartoDB positron")

if days <= 1:
    agg = df_period.groupby("commune").agg({
        "temp_ICON": "mean",
        "temp_min": "mean",
        "temp_max": "mean",
        "pluvio_GFS": "sum"
    }).reset_index()

    for _, row in agg.iterrows():
        commune = row['commune']
        lat = df[df["commune"] == commune]["latitude"].iloc[0]
        lon = df[df["commune"] == commune]["longitude"].iloc[0]
        popup_html = make_popup_single(row)

        folium.Marker(
            [lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            icon=folium.Icon(color="blue")
        ).add_to(m)

else:
    temp_min_daily = df_period.groupby(["commune", "date_day"])[