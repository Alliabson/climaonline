import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(page_title="Previsão Climática", layout="wide")

# Título do aplicativo
st.title("🌦️ App de Previsão Climática e Mapeamento")

# Usando uma chave de API pública (pode ter limites de uso)
DEFAULT_API_KEY = "f5cb0b965ea1564c50c6f1b74534d823"  # Substitua por sua própria chave

# Sidebar para configurações
with st.sidebar:
    st.header("Configurações")
    
    # Input para a chave da API com valor padrão
    api_key = st.text_input("Insira sua chave da API OpenWeatherMap:", 
                           value=DEFAULT_API_KEY,
                           type="password")
    
    # Seleção de unidades
    unit = st.radio("Unidades de temperatura:", ("Celsius", "Fahrenheit"))
    
    # Seleção de idioma
    lang = st.selectbox("Idioma:", ["pt", "en", "es"])

# Funções auxiliares
def get_units(unit):
    return "metric" if unit == "Celsius" else "imperial"

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
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados: {str(e)}")
        return None

def get_forecast_data(city, api_key, units, lang, days=5):
    base_url = "http://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": lang,
        "cnt": days * 8  # 8 previsões por dia (3 horas cada)
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter previsão: {str(e)}")
        return None

# Interface principal
tab1, tab2, tab3 = st.tabs(["Previsão Atual", "Previsão de 5 Dias", "Previsão Longo Prazo"])

with tab1:
    st.header("Previsão do Tempo Atual")
    city = st.text_input("Digite o nome da cidade:", key="current_city", value="São Paulo")
    
    if st.button("Buscar") or city:
        if not api_key:
            st.warning("Por favor, insira uma chave de API válida")
        else:
            weather_data = get_weather_data(city, api_key, get_units(unit), lang)
            
            if weather_data:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader(f"{weather_data['name']}, {weather_data['sys']['country']}")
                    st.metric("🌡️ Temperatura", f"{weather_data['main']['temp']}°{'C' if unit == 'Celsius' else 'F'}")
                    st.write(f"🌤️ Sensação: {weather_data['main']['feels_like']}°")
                    st.write(f"💧 Umidade: {weather_data['main']['humidity']}%")
                    st.write(f"🌬️ Vento: {weather_data['wind']['speed']} {'km/h' if unit == 'Celsius' else 'mph'}")
                    weather_desc = weather_data['weather'][0]['description'].capitalize()
                    st.write(f"📌 Condição: {weather_desc}")
                
                with col2:
                    map_center = [weather_data['coord']['lat'], weather_data['coord']['lon']]
                    m = folium.Map(location=map_center, zoom_start=10)
                    folium.Marker(
                        location=map_center,
                        popup=f"{weather_data['name']}",
                        tooltip="Clique para mais informações"
                    ).add_to(m)
                    folium_static(m, width=400, height=300)

with tab2:
    st.header("Previsão para 5 Dias")
    forecast_city = st.text_input("Digite o nome da cidade:", key="forecast_city", value="São Paulo")
    days = st.slider("Número de dias:", 1, 5, 5)
    
    if st.button("Buscar Previsão") or forecast_city:
        if not api_key:
            st.warning("Por favor, insira uma chave de API válida")
        else:
            forecast_data = get_forecast_data(forecast_city, api_key, get_units(unit), lang, days)
            
            if forecast_data:
                forecast_list = forecast_data['list']
                
                # Processar dados para DataFrame
                data = []
                for forecast in forecast_list:
                    dt = datetime.fromtimestamp(forecast['dt'])
                    data.append({
                        "Data": dt.strftime('%Y-%m-%d'),
                        "Hora": dt.strftime('%H:%M'),
                        "Temperatura": forecast['main']['temp'],
                        "Umidade": forecast['main']['humidity'],
                        "Condição": forecast['weather'][0]['description'].capitalize(),
                        "Vento": forecast['wind']['speed']
                    })
                
                df = pd.DataFrame(data)
                
                # Mostrar gráfico e tabela
                st.subheader(f"Previsão para {forecast_data['city']['name']}")
                st.line_chart(df.set_index('Data')['Temperatura'])
                st.dataframe(df)

with tab3:
    st.header("Previsão de Longo Prazo")
    st.warning("""
    ⚠️ A API gratuita do OpenWeatherMap só fornece previsão para 5 dias.
    Para previsões de longo prazo (até 12 meses), seria necessário:
    
    1. Usar uma API paga como a Climate Forecast API
    2. Ou implementar um modelo de machine learning com dados históricos
    
    Você pode testar APIs alternativas como:
    - Weatherbit (https://www.weatherbit.io/api)
    - Climacell (https://www.tomorrow.io/weather-api/)
    - Visual Crossing (https://www.visualcrossing.com/weather-api)
    """)
    
    # Simulação de dados históricos (apenas para demonstração)
    if st.button("Gerar Projeção (dados simulados)"):
        base_date = datetime.now()
        simulated_data = []
        
        for months in range(1, 13):
            date = base_date + timedelta(days=30*months)
            simulated_data.append({
                "Mês": date.strftime('%Y-%m'),
                "Temperatura Média": 20 + (months-6)*2,
                "Precipitação": 50 + (months-6)*10
            })
        
        df_simulated = pd.DataFrame(simulated_data)
        st.line_chart(df_simulated.set_index('Mês'))
        st.dataframe(df_simulated)

# Rodapé
st.markdown("---")
st.markdown("App desenvolvido com Python, Streamlit e OpenWeatherMap API")
