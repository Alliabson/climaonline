import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import pytz

# Configuração da página
st.set_page_config(page_title="Previsão Climática", layout="wide")

# Título do aplicativo
st.title("🌦️ App de Previsão Climática (Open-Meteo)")

# Funções para a API Open-Meteo
def get_current_weather(latitude, longitude, timezone="auto"):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": timezone,
        "forecast_days": 16  # Máximo permitido
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados: {str(e)}")
        return None

def get_city_coordinates(city_name):
    # Serviço de geocoding gratuito (poderia usar Nominatim também)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            return data["results"][0]
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao geocodificar cidade: {str(e)}")
        return None

# Interpretação dos códigos de tempo
WEATHER_CODES = {
    0: "Céu limpo",
    1: "Principalmente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com geada",
    51: "Chuvisco leve",
    53: "Chuvisco moderado",
    55: "Chuvisco denso",
    56: "Chuvisco congelante leve",
    57: "Chuvisco congelante denso",
    61: "Chuva leve",
    63: "Chuva moderada",
    65: "Chuva forte",
    66: "Chuva congelante leve",
    67: "Chuva congelante forte",
    71: "Queda de neve leve",
    73: "Queda de neve moderada",
    75: "Queda de neve forte",
    77: "Grãos de neve",
    80: "Pancadas de chuva leves",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva violentas",
    85: "Pancadas de neve leves",
    86: "Pancadas de neve fortes",
    95: "Trovoada leve ou moderada",
    96: "Trovoada com granizo leve",
    99: "Trovoada com granizo forte"
}

# Interface principal
tab1, tab2, tab3 = st.tabs(["Previsão Atual", "Previsão de 7 Dias", "Previsão de 16 Dias"])

with tab1:
    st.header("Previsão do Tempo Atual")
    city = st.text_input("Digite o nome da cidade:", key="current_city", value="São Paulo")
    
    if st.button("Buscar") or city:
        city_data = get_city_coordinates(city)
        
        if city_data:
            st.success(f"Localizado: {city_data['name']}, {city_data.get('admin1', '')}, {city_data.get('country', '')}")
            
            weather_data = get_current_weather(city_data["latitude"], city_data["longitude"])
            
            if weather_data:
                col1, col2 = st.columns(2)
                
                with col1:
                    current = weather_data["current"]
                    st.subheader(f"Condições Atuais")
                    st.metric("🌡️ Temperatura", f"{current['temperature_2m']}°C")
                    st.metric("💧 Umidade", f"{current['relative_humidity_2m']}%")
                    st.metric("🌬️ Vento", f"{current['wind_speed_10m']} km/h")
                    st.metric("🌧️ Precipitação", f"{current['precipitation']} mm")
                    st.write(f"📌 Condição: {WEATHER_CODES.get(current['weather_code'], 'Desconhecido')}")
                
                with col2:
                    map_center = [city_data["latitude"], city_data["longitude"]]
                    m = folium.Map(location=map_center, zoom_start=10)
                    folium.Marker(
                        location=map_center,
                        popup=f"{city_data['name']}",
                        tooltip="Clique para mais informações"
                    ).add_to(m)
                    folium_static(m, width=400, height=300)

with tab2:
    st.header("Previsão para 7 Dias")
    forecast_city = st.text_input("Digite o nome da cidade:", key="forecast_city", value="São Paulo")
    
    if st.button("Buscar Previsão Semanal") or forecast_city:
        city_data = get_city_coordinates(forecast_city)
        
        if city_data:
            weather_data = get_current_weather(city_data["latitude"], city_data["longitude"])
            
            if weather_data and "daily" in weather_data:
                daily = weather_data["daily"]
                dates = pd.to_datetime(daily["time"])
                df = pd.DataFrame({
                    "Data": dates,
                    "Máxima": daily["temperature_2m_max"],
                    "Mínima": daily["temperature_2m_min"],
                    "Precipitação (mm)": daily["precipitation_sum"],
                    "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
                }).head(7)  # Mostrar apenas 7 dias
                
                st.subheader(f"Previsão para {city_data['name']}")
                st.line_chart(df.set_index("Data")[["Máxima", "Mínima"]])
                st.dataframe(df)

with tab3:
    st.header("Previsão para 16 Dias")
    st.info("Esta é a previsão estendida máxima disponível na API gratuita Open-Meteo")
    
    extended_city = st.text_input("Digite o nome da cidade:", key="extended_city", value="São Paulo")
    
    if st.button("Buscar Previsão Estendida") or extended_city:
        city_data = get_city_coordinates(extended_city)
        
        if city_data:
            weather_data = get_current_weather(city_data["latitude"], city_data["longitude"])
            
            if weather_data and "daily" in weather_data:
                daily = weather_data["daily"]
                dates = pd.to_datetime(daily["time"])
                df = pd.DataFrame({
                    "Data": dates,
                    "Máxima": daily["temperature_2m_max"],
                    "Mínima": daily["temperature_2m_min"],
                    "Precipitação (mm)": daily["precipitation_sum"],
                    "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
                })
                
                st.subheader(f"Previsão para {city_data['name']}")
                
                # Gráfico de temperatura
                st.write("### Temperaturas Máximas e Mínimas")
                st.line_chart(df.set_index("Data")[["Máxima", "Mínima"]])
                
                # Gráfico de precipitação
                st.write("### Precipitação Acumulada")
                st.bar_chart(df.set_index("Data")["Precipitação (mm)"])
                
                # Tabela completa
                st.write("### Detalhes Diários")
                st.dataframe(df)

# Rodapé
st.markdown("---")
st.markdown("App desenvolvido com Python, Streamlit e Open-Meteo API")
