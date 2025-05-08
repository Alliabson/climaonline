import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta

# Configuração da página
st.set_page_config(page_title="Previsão Climática Premium", layout="wide")

# Título do aplicativo
st.title("🌦️ App de Previsão Climática com Monitoramento de Eventos Extremos")

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

# Funções para a API Open-Meteo
def get_city_options(city_name):
    """Obtém todas as cidades com o nome pesquisado (case-insensitive)"""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name.lower()}&count=20&language=pt"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("results"):
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
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant",
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

def get_historical_weather_data(latitude, longitude, start_date, end_date):
    """Obtém dados históricos para análise de eventos extremos"""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", 
                 "wind_speed_10m_max", "wind_direction_10m_dominant"],
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados históricos: {str(e)}")
        return None

def detect_extreme_events(weather_data):
    """Identifica eventos climáticos extremos nos dados"""
    extreme_events = []
    threshold = {
        'precipitation': 50,  # mm/dia
        'wind_speed': 60,     # km/h
        'heat_wave': 35,      # °C máxima por 3+ dias
        'cold_wave': 5        # °C mínima por 3+ dias
    }
    
    daily_data = weather_data.get('daily', {})
    dates = daily_data.get('time', [])
    
    for i in range(len(dates)):
        event = {
            'date': dates[i],
            'events': []
        }
        
        # Verificar precipitação extrema
        precip_value = daily_data.get('precipitation_sum', [0]*len(dates))[i] or 0
        if precip_value > threshold['precipitation']:
            event['events'].append(f"Precipitação extrema: {daily_data['precipitation_sum'][i]} mm")
        
        # Verificar ventos fortes
        wind_value = daily_data.get('wind_speed_10m_max', [0]*len(dates))[i] or 0
        if wind_value > threshold['wind_speed']:
            direction = daily_data.get('wind_direction_10m_dominant', [0]*len(dates))[i]
            event['events'].append(f"Rajada de vento: {daily_data['wind_speed_10m_max'][i]} km/h, direção {direction}°")
        
        # Verificar ondas de calor/frio
        if i >= 2:
            if all((daily_data.get('temperature_2m_max', [0]*len(dates))[j] or 0) >= threshold['heat_wave'] for j in range(i-2, i+1)):
                event['events'].append("Onda de calor detectada")
            if all((daily_data.get('temperature_2m_min', [0]*len(dates))[j] or 0) <= threshold['cold_wave'] for j in range(i-2, i+1)):
                event['events'].append("Onda de frio detectada")
        
        if event['events']:
            extreme_events.append(event)
    
    return extreme_events

def get_satellite_images(latitude, longitude, date):
    """Obtém imagens de satélite próximas à data do evento (simulado)"""
    return {
        'image_url': f"https://maps.googleapis.com/maps/api/staticmap?center={latitude},{longitude}&zoom=10&size=600x300&maptype=hybrid&markers=color:red%7C{latitude},{longitude}&key=YOUR_API_KEY",
        'source': "Google Maps Satellite (simulado)",
        'date': date
    }

def generate_technical_report(event_data, city_data, satellite_images=None):
    """Gera um laudo técnico para eventos extremos"""
    report = {
        'title': f"Laudo Técnico de Evento Climático Extremo - {city_data['name']}",
        'date': datetime.now().strftime("%Y-%m-%d"),
        'location': city_data,
        'events': event_data,
        'satellite_images': satellite_images,
        'analysis': "",
        'recommendations': ""
    }
    
    # Análise automática básica
    for event in event_data:
        for e in event['events']:
            if "Precipitação extrema" in e:
                report['analysis'] += f"\n- Evento de precipitação intensa em {event['date']} pode indicar risco de alagamentos ou deslizamentos."
            elif "Rajada de vento" in e:
                report['analysis'] += f"\n- Rajadas de vento em {event['date']} podem ter causado danos a estruturas e vegetação."
            elif "Onda de calor" in e:
                report['analysis'] += f"\n- Período prolongado de calor em {event['date']} com impactos na saúde e consumo energético."
            elif "Onda de frio" in e:
                report['analysis'] += f"\n- Período prolongado de frio em {event['date']} com risco para agricultura e população vulnerável."
    
    # Recomendações genéricas
    report['recommendations'] = """
    - Verificar estruturas físicas quanto a danos
    - Monitorar áreas de risco para eventos futuros
    - Acompanhar atualizações meteorológicas
    - Implementar planos de contingência conforme necessário
    """
    
    return report

def generate_pdf_report(report):
    """Gera um PDF do laudo técnico (simulado)"""
    # Simulação - na prática use ReportLab ou WeasyPrint
    pdf_content = f"""
    LAUDO TÉCNICO
    {report['title']}
    
    Data: {report['date']}
    Local: {report['location']['name']}, {report['location'].get('admin1', '')}
    
    EVENTOS DETECTADOS:
    {"".join(f"- {event['date']}: {', '.join(event['events'])}\n" for event in report['events'])}
    
    ANÁLISE TÉCNICA:
    {report['analysis']}
    
    RECOMENDAÇÕES:
    {report['recommendations']}
    """
    return pdf_content.encode()

# Funções de exibição
def show_current_weather(city_data, weather_data):
    """Mostra a previsão atual"""
    st.header("⏱️ Previsão do Tempo Atual")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        current = weather_data["current"]
        st.subheader(f"Condições Atuais em {city_data['name']}")
        
        cols = st.columns(3)
        cols[0].metric("🌡️ Temperatura", f"{current['temperature_2m']}°C")
        cols[1].metric("💧 Umidade", f"{current['relative_humidity_2m']}%")
        cols[2].metric("🌬️ Vento", f"{current['wind_speed_10m']} km/h")
        
        cols = st.columns(3)
        cols[0].metric("🧭 Direção Vento", f"{current['wind_direction_10m']}°")
        cols[1].metric("🌧️ Precipitação", f"{current['precipitation']} mm")
        cols[2].metric("📌 Condição", WEATHER_CODES.get(current['weather_code'], "Desconhecido"))
    
    with col2:
        map_center = [city_data["latitude"], city_data["longitude"]]
        m = folium.Map(location=map_center, zoom_start=10)
        folium.Marker(
            location=map_center,
            popup=f"{city_data['name']}",
            tooltip="Local analisado",
            icon=folium.Icon(color="red")
        ).add_to(m)
        folium_static(m, width=350, height=300)

def show_weekly_forecast(city_data, weather_data):
    """Mostra a previsão de 7 dias"""
    st.header(f"📅 Previsão para 7 Dias em {city_data['name']}")
    
    if "daily" in weather_data:
        daily = weather_data["daily"]
        dates = pd.to_datetime(daily["time"])
        
        df = pd.DataFrame({
            "Data": dates,
            "Máxima (°C)": daily["temperature_2m_max"],
            "Mínima (°C)": daily["temperature_2m_min"],
            "Precipitação (mm)": daily["precipitation_sum"],
            "Vento (km/h)": daily["wind_speed_10m_max"],
            "Direção Vento": daily["wind_direction_10m_dominant"],
            "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
        }).head(7)
        
        st.line_chart(df.set_index("Data")[["Máxima (°C)", "Mínima (°C)"]])
        st.dataframe(df.style.background_gradient(cmap='coolwarm', subset=["Precipitação (mm)", "Vento (km/h)"]))
        
        # Alertas para próximos eventos
        upcoming_events = detect_extreme_events({
            "daily": {k: v[:7] for k, v in daily.items()}
        })
        
        if upcoming_events:
            st.warning("⚠️ Alertas para os próximos dias:")
            for event in upcoming_events:
                st.write(f"- {event['date']}: {', '.join(event['events'])}")

def show_extended_forecast(city_data, weather_data):
    """Mostra a previsão de 16 dias"""
    st.header(f"📊 Previsão Estendida para 16 Dias em {city_data['name']}")
    st.info("Esta é a previsão máxima disponível na API Open-Meteo")
    
    if "daily" in weather_data:
        daily = weather_data["daily"]
        dates = pd.to_datetime(daily["time"])
        
        df = pd.DataFrame({
            "Data": dates,
            "Máxima (°C)": daily["temperature_2m_max"],
            "Mínima (°C)": daily["temperature_2m_min"],
            "Precipitação (mm)": daily["precipitation_sum"],
            "Vento Máx (km/h)": daily["wind_speed_10m_max"],
            "Direção Vento": daily["wind_direction_10m_dominant"],
            "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
        })
        
        tab1, tab2, tab3 = st.tabs(["Temperaturas", "Precipitação", "Ventos"])
        
        with tab1:
            st.line_chart(df.set_index("Data")[["Máxima (°C)", "Mínima (°C)"]])
        
        with tab2:
            st.bar_chart(df.set_index("Data")["Precipitação (mm)"])
        
        with tab3:
            st.bar_chart(df.set_index("Data")["Vento Máx (km/h)"])
        
        st.write("### Detalhes Diários")
        st.dataframe(df.style.background_gradient(cmap='coolwarm', subset=["Precipitação (mm)", "Vento Máx (km/h)"]))

def show_extreme_events(city_data, weather_data):
    """Mostra eventos extremos detectados"""
    st.header("⚠️ Monitoramento de Eventos Extremos")
    
    # Obter dados históricos dos últimos 30 dias
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    with st.spinner("Analisando dados históricos..."):
        historical_data = get_historical_weather_data(
            city_data["latitude"],
            city_data["longitude"],
            start_date,
            end_date
        )
    
    if historical_data:
        extreme_events = detect_extreme_events(historical_data)
        
        if extreme_events:
            st.warning(f"🔴 Foram detectados {len(extreme_events)} eventos extremos nos últimos 30 dias")
            
            for event in extreme_events:
                with st.expander(f"📅 Evento em {event['date']}", expanded=False):
                    st.error("Eventos detectados:")
                    for e in event['events']:
                        st.write(f"- 🔥 {e}")
                    
                    # Obter imagem de satélite aproximada
                    satellite_img = get_satellite_images(
                        city_data["latitude"],
                        city_data["longitude"],
                        event['date']
                    )
                    
                    st.image(satellite_img['image_url'], 
                            caption=f"🌍 Imagem de satélite aproximada - {satellite_img['source']} ({event['date']})")
                    
                    # Botão para gerar laudo
                    if st.button(f"📝 Gerar Laudo Técnico para {event['date']}", key=f"report_{event['date']}"):
                        report = generate_technical_report([event], city_data, [satellite_img])
                        
                        st.subheader("📄 Laudo Técnico")
                        st.write(f"**Local:** {report['location']['name']}, {report['location'].get('admin1', '')}")
                        st.write(f"**Data do Evento:** {event['date']}")
                        st.write(f"**Data do Laudo:** {report['date']}")
                        
                        st.subheader("📊 Análise Técnica")
                        st.write(report['analysis'])
                        
                        st.subheader("🛡️ Recomendações")
                        st.write(report['recommendations'])
                        
                        # Opção para download do laudo
                        st.download_button(
                            label="⬇️ Download do Laudo (TXT)",
                            data=generate_pdf_report(report),
                            file_name=f"laudo_{city_data['name']}_{event['date']}.txt",
                            mime="text/plain"
                        )
        else:
            st.success("✅ Nenhum evento extremo detectado nos últimos 30 dias")
    else:
        st.error("❌ Não foi possível obter dados históricos para análise")

# Interface principal
def main():
    # Barra lateral com informações corporativas
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Weather+Pro", width=150)
        st.markdown("### Serviços Profissionais")
        st.markdown("""
        - Monitoramento de eventos extremos
        - Laudos técnicos personalizados
        - Alertas em tempo real
        - API para integração corporativa
        """)
        
        st.markdown("### Planos Disponíveis")
        st.markdown("""
        - **Básico**: Previsões padrão
        - **Profissional**: + Eventos extremos
        - **Corporativo**: + Laudos + API
        """)
        
        st.markdown("---")
        st.markdown("📞 Contato: contato@weatherpro.com")
        st.markdown("🌐 www.weatherpro.com")

    tab1, tab2, tab3, tab4 = st.tabs([
        "⏱️ Atual", 
        "📅 7 Dias", 
        "📊 16 Dias",
        "⚠️ Eventos Extremos"
    ])

    # Pesquisa de cidade
    city_name = st.text_input("🔍 Digite o nome da cidade:", value="São Paulo", key="city_search")
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
                "📍 Selecione a localidade correta:",
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
                # Abas de previsão
                with tab1:
                    show_current_weather(city_data, weather_data)
                
                with tab2:
                    show_weekly_forecast(city_data, weather_data)
                
                with tab3:
                    show_extended_forecast(city_data, weather_data)
                
                # Nova aba para eventos extremos
                with tab4:
                    show_extreme_events(city_data, weather_data)
        else:
            st.warning("⚠️ Nenhuma cidade encontrada com esse nome. Tente novamente.")

if __name__ == "__main__":
    main()

# Rodapé
st.markdown("---")
st.markdown("App desenvolvido com Python, Streamlit e Open-Meteo e WeatherPro - Soluções em Monitoramento Climático Corporativo -  API Alliabson @2025")
