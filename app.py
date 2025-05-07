import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Previsão Climática e Mapeamento", layout="wide")

# Título do aplicativo
st.title("🌦️ App de Previsão Climática e Mapeamento")

# Sidebar para configurações
with st.sidebar:
    st.header("Configurações")
    
    # Input para a chave da API (você pode hardcodear se preferir)
    api_key = st.text_input("Insira sua chave da API OpenWeatherMap:", type="password")
    
    # Seleção de unidades
    unit = st.radio("Unidades de temperatura:", ("Celsius", "Fahrenheit"))
    
    # Seleção de idioma
    lang = st.selectbox("Idioma:", ["pt", "en", "es", "fr"])

# Função para converter unidades para o formato da API
def get_units(unit):
    return "metric" if unit == "Celsius" else "imperial"

# Função para obter dados climáticos
def get_weather_data(city, api_key, units, lang):
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": lang
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Verifica se há erros
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados: {e}")
        return None

# Função para obter previsão de 5 dias
def get_forecast_data(city, api_key, units, lang):
    base_url = "http://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": lang,
        "cnt": 40  # Número de previsões (5 dias a cada 3 horas)
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter previsão: {e}")
        return None

# Interface principal
tab1, tab2 = st.tabs(["Previsão Atual", "Previsão de 5 Dias"])

with tab1:
    st.header("Previsão do Tempo Atual")
    city = st.text_input("Digite o nome da cidade:", key="current_city")
    
    if city and api_key:
        weather_data = get_weather_data(city, api_key, get_units(unit), lang)
        
        if weather_data:
            col1, col2 = st.columns(2)
            
            with col1:
                # Exibindo informações básicas
                st.subheader(f"{weather_data['name']}, {weather_data['sys']['country']}")
                st.write(f"🌡️ Temperatura: {weather_data['main']['temp']}°{'C' if unit == 'Celsius' else 'F'}")
                st.write(f"🌤️ Sensação térmica: {weather_data['main']['feels_like']}°{'C' if unit == 'Celsius' else 'F'}")
                st.write(f"💧 Umidade: {weather_data['main']['humidity']}%")
                st.write(f"🌬️ Vento: {weather_data['wind']['speed']} {'km/h' if unit == 'Celsius' else 'mph'}")
                
                # Descrição do tempo
                weather_desc = weather_data['weather'][0]['description'].capitalize()
                st.write(f"📌 Condição: {weather_desc}")
                
            with col2:
                # Mapa da localização
                map_center = [weather_data['coord']['lat'], weather_data['coord']['lon']]
                m = folium.Map(location=map_center, zoom_start=10)
                
                # Marcador no mapa
                folium.Marker(
                    location=map_center,
                    popup=f"{weather_data['name']}",
                    tooltip="Clique para mais informações"
                ).add_to(m)
                
                # Exibir o mapa
                folium_static(m, width=400, height=300)

with tab2:
    st.header("Previsão para 5 Dias")
    forecast_city = st.text_input("Digite o nome da cidade:", key="forecast_city")
    
    if forecast_city and api_key:
        forecast_data = get_forecast_data(forecast_city, api_key, get_units(unit), lang)
        
        if forecast_data:
            # Processar os dados da previsão
            forecast_list = forecast_data['list']
            dates = []
            temps = []
            humidity = []
            conditions = []
            
            for forecast in forecast_list:
                date_time = datetime.fromtimestamp(forecast['dt'])
                date = date_time.strftime('%Y-%m-%d')
                time = date_time.strftime('%H:%M')
                
                dates.append(date)
                temps.append(forecast['main']['temp'])
                humidity.append(forecast['main']['humidity'])
                conditions.append(forecast['weather'][0]['description'].capitalize())
            
            # Criar DataFrame com os dados
            df = pd.DataFrame({
                "Data": dates,
                "Hora": [datetime.fromtimestamp(f['dt']).strftime('%H:%M') for f in forecast_list],
                "Temperatura": temps,
                "Umidade": humidity,
                "Condição": conditions
            })
            
            # Agrupar por dia para exibição
            st.subheader(f"Previsão para {forecast_data['city']['name']}, {forecast_data['city']['country']}")
            
            # Mostrar gráfico de temperatura
            st.line_chart(df.set_index('Data')['Temperatura'])
            
            # Mostrar tabela com detalhes
            st.write("Detalhes da previsão:")
            st.dataframe(df)

# Rodapé
st.markdown("---")
st.markdown("App desenvolvido com Python, Streamlit e OpenWeatherMap API")
