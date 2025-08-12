import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

st.set_page_config(page_title="Météo Grand Est", layout="wide")

# ----------------------------
# Grandes villes du Grand Est
# ----------------------------
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

# ----------------------------
# Récupération météo
# ----------------------------
@st.cache_data(show_spinner="Chargement météo...")
def get_weather_data():
    session = requests.Session()
    session.headers.update({"User-Agent": "meteo-grand-est"})

    results = []
    for city in GRAND_EST_CITIES:
        params = {
            'latitude': city['lat'],
            'longitude': city['lon'],
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

# ----------------------------
# Agrégation journalière
# ----------------------------
@st.cache_data
def compute_daily_stats(df):
    return (
        df.groupby(["ville", "latitude", "longitude", "date"])
          .agg(
              temp_mean=("temp", "mean"),
              temp_max=("temp", "max"),
              temp_min=("temp", "min"),
              precip_mean=("precip", "mean"),
              precip_max=("precip", "max"),
              precip_min=("precip", "min"),
              precip_sum=("precip", "sum"),
          )
          .reset_index()
    )

# ----------------------------
# Application Streamlit
# ----------------------------
st.markdown("### Météo - Grandes villes du Grand Est")

df = get_weather_data()

if df.empty:
    st.error("Impossible de récupérer les données météo.")
else:
    stats_df = compute_daily_stats(df)

    # Sélection de la date
    selected_date = st.selectbox(
        "Choisissez une date",
        sorted(stats_df["date"].unique())
    )

    daily_data = stats_df[stats_df["date"] == selected_date]

    # ----------------------------
    # Carte Folium
    # ----------------------------
    m = folium.Map(location=[48.5, 6.5], zoom_start=7)
    marker_cluster = MarkerCluster().add_to(m)

    for _, row in daily_data.iterrows():
        popup_html = f"""
        <b>{row['ville']}</b><br>
        🌡️ Température moy : {row['temp_mean']:.1f} °C<br>
        🌡️ Max : {row['temp_max']:.1f} °C / Min : {row['temp_min']:.1f} °C<br>
        ☔ Pluie moy : {row['precip_mean']:.1f} mm<br>
        ☔ Max : {row['precip_max']:.1f} mm / Min : {row['precip_min']:.1f} mm<br>
        🌧️ Pluie totale : {row['precip_sum']:.1f} mm
        """
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=popup_html,
            icon=folium.Icon(color="blue", icon="cloud")
        ).add_to(marker_cluster)

    st_folium(m, width=900, height=600)
