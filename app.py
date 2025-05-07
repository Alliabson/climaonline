import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(page_title="Previsão Climática", layout="wide")

# Título do aplicativo
st.title("🌦️ App de Previsão Climática (Open-Meteo)")

# Funções para a API Open-Meteo
def get_city_options(city_name):
    """Obtém todas as cidades com o nome pesquisado (case-insensitive)"""
    # Converter para minúsculas para padronizar, mas manter a busca original
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name.lower()}&count=20&language=pt"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Manter a formatação original dos nomes das cidades
        if data.get("results"):
            # Filtro adicional para garantir match case-insensitive
            filtered_results = [
                city for city in data["results"] 
                if city['name'].lower() == city_name.lower()
            ]
            return filtered_results if filtered_results else data["results"]
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar cidades: {str(e)}")
        return []

def get_weather_data(latitude, longitude, timezone="auto", forecast_days=16):
    """Obtém dados meteorológicos para as coordenadas"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": timezone,
        "forecast_days": forecast_days
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados meteorológicos: {str(e)}")
        return None

# Dicionário de códigos de tempo (traduzido para português)
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
def main():
    tab1, tab2, tab3 = st.tabs(["Previsão Atual", "Previsão de 7 Dias", "Previsão de 16 Dias"])

    # Pesquisa de cidade
    city_name = st.text_input("Digite o nome da cidade:", value=" ", key="city_search")
    
    if city_name:
        city_options = get_city_options(city_name)
        
        if city_options:
            # Criar lista de opções formatadas
            options = [
                f"{city['name']}, {city.get('admin1', '')}, {city.get('country', '')} (Lat: {city['latitude']:.2f}, Lon: {city['longitude']:.2f})"
                for city in city_options
            ]
            
            # Selecionador de cidade
            selected_city = st.selectbox(
                "Foram encontradas várias cidades com esse nome. Selecione a localidade correta:",
                options,
                index=0
            )
            
            # Obter índice da cidade selecionada
            selected_index = options.index(selected_city)
            city_data = city_options[selected_index]
            
            # Obter dados meteorológicos
            weather_data = get_weather_data(
                city_data["latitude"],
                city_data["longitude"],
                city_data.get("timezone", "auto")
            )
            
            if weather_data:
                # Aba de previsão atual
                with tab1:
                    show_current_weather(city_data, weather_data)
                
                # Aba de previsão de 7 dias
                with tab2:
                    show_weekly_forecast(city_data, weather_data)
                
                # Aba de previsão de 16 dias
                with tab3:
                    show_extended_forecast(city_data, weather_data)
        else:
            st.warning("Nenhuma cidade encontrada com esse nome. Tente novamente.")

def show_current_weather(city_data, weather_data):
    """Mostra a previsão atual"""
    st.header("Previsão do Tempo Atual")
    
    col1, col2 = st.columns(2)
    
    with col1:
        current = weather_data["current"]
        st.subheader(f"Condições Atuais em {city_data['name']}")
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
            popup=f"{city_data['name']}, {city_data.get('admin1', '')}",
            tooltip="Clique para mais informações",
            icon=folium.Icon(color="blue")
        ).add_to(m)
        folium_static(m, width=400, height=300)

def show_weekly_forecast(city_data, weather_data):
    """Mostra a previsão de 7 dias"""
    st.header(f"Previsão para 7 Dias em {city_data['name']}")
    
    if "daily" in weather_data:
        daily = weather_data["daily"]
        dates = pd.to_datetime(daily["time"])
        
        df = pd.DataFrame({
            "Data": dates,
            "Máxima (°C)": daily["temperature_2m_max"],
            "Mínima (°C)": daily["temperature_2m_min"],
            "Precipitação (mm)": daily["precipitation_sum"],
            "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
        }).head(7)  # Mostrar apenas 7 dias
        
        st.line_chart(df.set_index("Data")[["Máxima (°C)", "Mínima (°C)"]])
        st.dataframe(df)

def show_extended_forecast(city_data, weather_data):
    """Mostra a previsão de 16 dias"""
    st.header(f"Previsão Estendida para 16 Dias em {city_data['name']}")
    st.info("Esta é a previsão máxima disponível na API gratuita Open-Meteo")
    
    if "daily" in weather_data:
        daily = weather_data["daily"]
        dates = pd.to_datetime(daily["time"])
        
        df = pd.DataFrame({
            "Data": dates,
            "Máxima (°C)": daily["temperature_2m_max"],
            "Mínima (°C)": daily["temperature_2m_min"],
            "Precipitação (mm)": daily["precipitation_sum"],
            "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
        })
        
        st.write("### Temperaturas Máximas e Mínimas")
        st.line_chart(df.set_index("Data")[["Máxima (°C)", "Mínima (°C)"]])
        
        st.write("### Precipitação Acumulada")
        st.bar_chart(df.set_index("Data")["Precipitação (mm)"])
        
        st.write("### Detalhes Diários")
        st.dataframe(df)

if __name__ == "__main__":
    main()

# Rodapé
st.markdown("---")
st.markdown("App desenvolvido com Python, Streamlit e Open-Meteo API Alliabson @2025")
