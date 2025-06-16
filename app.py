import streamlit as st
import requests
import pandas as pd
from io import StringIO
import folium
from streamlit_folium import folium_static, st_folium
from datetime import datetime, timedelta
import sqlite3
from folium import plugins
import tempfile
from fpdf import FPDF
import os
from functools import partial
from dotenv import load_dotenv
import plotly.express as px
import math

# Carregar variáveis de ambiente
load_dotenv()
NASA_API_KEY = os.getenv("NASA_API_KEY", "de744659515921a11cf8cabac3dfed1e")
NASA_FIRMS_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_NOAA20_NRT/{area}/1/{date}"

# --- CONFIGURAÇÃO DA PÁGINA E ESTILOS ---
st.set_page_config(page_title="Previsão Climática Premium", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* Estilos globais e de corpo */
.stApp {
    background-color: #F0F2F6; /* Cor de fundo suave */
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #262730;
}

/* Título principal do aplicativo */
.stTitle {
    color: #1E88E5; /* Azul vibrante */
    text-align: center;
    margin-bottom: 30px;
    font-size: 2.5em;
    font-weight: bold;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}

/* Seções e cabeçalhos */
h1, h2, h3, h4, h5, h6 {
    color: #1E88E5;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
    border-bottom: 2px solid rgba(30, 136, 229, 0.2); /* Linha sutil */
    padding-bottom: 5px;
}

/* Cards/Métricas para informações atuais */
.stMetric {
    background-color: white;
    padding: 15px 20px;
    border-radius: 12px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1); /* Sombra mais pronunciada */
    margin-bottom: 15px;
    transition: transform 0.2s; /* Efeito hover */
}
.stMetric:hover {
    transform: translateY(-3px);
}

/* Estilo para abas */
.stTabs [data-baseweb="tab-list"] {
    gap: 15px; /* Espaçamento entre as abas */
}
.stTabs [data-baseweb="tab-list"] button {
    padding: 10px 20px;
    background-color: #E0E0E0; /* Cor de fundo das abas inativas */
    border-radius: 8px 8px 0 0;
    font-weight: bold;
    color: #555;
    transition: background-color 0.3s, color 0.3s;
}
.stTabs [data-baseweb="tab-list"] button:hover {
    background-color: #D0D0D0;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    background-color: #1E88E5; /* Cor da aba selecionada */
    color: white;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
    color: white; /* Cor do texto da aba selecionada */
}

/* Estilo para botões */
.stButton>button {
    background-color: #1E88E5;
    color: white;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    transition: background-color 0.3s, transform 0.2s;
}
.stButton>button:hover {
    background-color: #1565C0;
    transform: translateY(-2px);
}

/* Expander */
.stExpander {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    margin-bottom: 10px;
}
.stExpander details summary {
    font-weight: bold;
    color: #1E88E5;
}

/* Rodapé */
.footer {
    font-size: 13px;
    text-align: center;
    color: #888;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #E0E0E0;
}
</style>
""", unsafe_allow_html=True)

st.title("🌦️ App de Previsão Climática Avançado")

# Dicionário de códigos de tempo (traduzido para português)
WEATHER_CODES = {
    0: "Céu limpo", 1: "Principalmente limpo", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Nevoeiro", 48: "Nevoeiro com geada", 51: "Chuvisco leve", 53: "Chuvisco moderado",
    55: "Chuvisco denso", 56: "Chuvisco congelante leve", 57: "Chuvisco congelante denso",
    61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva forte", 66: "Chuva congelante leve",
    67: "Chuva congelante forte", 71: "Queda de neve leve", 73: "Queda de neve moderada",
    75: "Queda de neve forte", 77: "Grãos de neve", 80: "Pancadas de chuva leves",
    81: "Pancadas de chuva moderadas", 82: "Pancadas de chuva violentas", 85: "Pancadas de neve leves",
    86: "Pancadas de neve fortes", 95: "Trovoada leve ou moderada", 96: "Trovoada com granizo leve",
    99: "Trovoada com granizo forte"
}

# Inicializar banco de dados SQLite
def init_db():
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 city TEXT,
                 date TEXT,
                 event_date TEXT,
                 report_type TEXT,
                 pdf_content BLOB,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Funções da API Open-Meteo
@st.cache_data(ttl=3600) # Cache por 1 hora
def get_city_options(city_name):
    """Obtém opções de cidades a partir do nome pesquisado."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name.lower()}&count=20&language=pt"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            filtered_results = [city for city in data["results"] if city['name'].lower() == city_name.lower()]
            return filtered_results if filtered_results else data["results"]
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar cidades: {str(e)}")
        return []

@st.cache_data(ttl=600) # Cache por 10 minutos
def get_weather_data(latitude, longitude, timezone="auto", forecast_days=16):
    """Obtém dados meteorológicos para as coordenadas."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,uv_index",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,uv_index",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,uv_index_max,sunrise,sunset",
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

@st.cache_data(ttl=3600) # Cache por 1 hora
def get_historical_weather_data(latitude, longitude, start_date, end_date):
    """Obtém dados históricos para análise de eventos extremos."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude, "longitude": longitude,
        "start_date": start_date, "end_date": end_date,
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

@st.cache_data(ttl=3600) # Cache por 1 hora
def get_air_quality_data(latitude, longitude):
    """Obtém dados de qualidade do ar para as coordenadas (Open-Meteo Air Quality)."""
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
        "timezone": "auto"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.warning(f"Não foi possível obter dados de qualidade do ar: {str(e)}")
        return None

def detect_extreme_events(weather_data):
    """Identifica eventos climáticos extremos nos dados."""
    extreme_events = []
    threshold = {
        'precipitation': 50, # mm/dia
        'wind_speed': 60,    # km/h
        'heat_wave': 35,     # °C máxima por 3+ dias
        'cold_wave': 5       # °C mínima por 3+ dias
    }
    daily_data = weather_data.get('daily', {})
    dates = daily_data.get('time', [])
    for i in range(len(dates)):
        event = {'date': dates[i], 'events': []}
        precip_value = daily_data.get('precipitation_sum', [0]*len(dates))[i] or 0
        if precip_value > threshold['precipitation']:
            event['events'].append(f"Precipitação extrema: {precip_value} mm")
        wind_value = daily_data.get('wind_speed_10m_max', [0]*len(dates))[i] or 0
        if wind_value > threshold['wind_speed']:
            direction = daily_data.get('wind_direction_10m_dominant', [0]*len(dates))[i]
            event['events'].append(f"Rajada de vento: {wind_value} km/h, direção {direction}°")
        if i >= 2:
            if all((daily_data.get('temperature_2m_max', [0]*len(dates))[j] or 0) >= threshold['heat_wave'] for j in range(i-2, i+1)):
                event['events'].append("Onda de calor detectada")
            if all((daily_data.get('temperature_2m_min', [0]*len(dates))[j] or 0) <= threshold['cold_wave'] for j in range(i-2, i+1)):
                event['events'].append("Onda de frio detectada")
        if event['events']:
            extreme_events.append(event)
    return extreme_events

def get_satellite_images(latitude, longitude, date):
    """Obtém imagens de satélite próximas à data do evento (simulado para este exemplo)."""
    return {
        'image_url': f"https://via.placeholder.com/600x300?text=Imagem+Sat%C3%A9lite+{date}",
        'source': "Google Maps Satellite (simulado)",
        'date': date
    }

@st.cache_data(ttl=3600)
def create_weather_map(latitude, longitude, city_name, weather_data=None, fire_data=None, air_quality_data=None):
    """Cria um mapa meteorológico interativo com camadas."""
    m = folium.Map(
        location=[latitude, longitude],
        zoom_start=10,
        tiles='OpenStreetMap',
        attr='OpenStreetMap',
        control_scale=True
    )

    folium.Marker(
        location=[latitude, longitude],
        popup=f"<b>{city_name}</b>",
        icon=folium.Icon(color='red', icon='cloud', prefix='fa')
    ).add_to(m)

    # Camada de Temperatura Horária (para as próximas 24h, amostrada)
    if weather_data and 'hourly' in weather_data:
        temperature_layer = folium.FeatureGroup(name='Temperatura Horária (Próx. 24h)', show=False).add_to(m)
        for i in range(0, min(len(weather_data['hourly']['time']), 24), 3):
            temp = weather_data['hourly']['temperature_2m'][i]
            time_str = weather_data['hourly']['time'][i]
            if temp is not None:
                color = 'blue' if temp < 10 else 'green' if temp < 20 else 'orange' if temp < 30 else 'red'
                offset_lat = 0.01 * math.sin(i * math.pi / 4)
                offset_lon = 0.01 * math.cos(i * math.pi / 4)
                folium.CircleMarker(
                    location=[latitude + offset_lat, longitude + offset_lon],
                    radius=5,
                    popup=f"Temp: {temp}°C<br>Hora: {time_str}",
                    color=color,
                    fill=True,
                    fill_opacity=0.7
                ).add_to(temperature_layer)

    # Camada de Precipitação Diária (próximos 7 dias)
    if weather_data and 'daily' in weather_data:
        precipitation_layer = folium.FeatureGroup(name='Precipitação Diária (Próx. 7 dias)', show=False).add_to(m)
        for i, precip in enumerate(weather_data['daily']['precipitation_sum'][:7]):
            if precip is not None and float(precip) > 0:
                radius_size = max(5, min(float(precip) * 2, 30))
                offset_lat = 0.02 * i
                offset_lon = 0.02 * i
                folium.Circle(
                    location=[latitude - offset_lat, longitude + offset_lon],
                    radius=radius_size,
                    popup=f"Precipitação: {precip}mm",
                    color='blue',
                    fill=True,
                    fill_opacity=0.3
                ).add_to(precipitation_layer)

    # Camada de Focos de Incêndio (Cluster)
    if fire_data is not None and not fire_data.empty and 'latitude' in fire_data.columns and 'longitude' in fire_data.columns:
        fire_data = fire_data.head(200)
        marker_cluster = plugins.MarkerCluster(name='Focos de Incêndio (últimos 7 dias)').add_to(m)
        for idx, row in fire_data.iterrows():
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=f"Foco em {row.get('acq_date', 'N/A')}<br>Confiança: {row.get('confidence', 'N/A')}%",
                icon=folium.Icon(color='darkred', icon='fire', prefix='fa')
            ).add_to(marker_cluster)
    else:
        folium.FeatureGroup(name='Sem Focos de Incêndio (7 dias)').add_to(m)

    # Camada de Qualidade do Ar (ponto colorido para o valor mais recente)
    if air_quality_data and air_quality_data.get('hourly'):
        aq_layer = folium.FeatureGroup(name='Qualidade do Ar (PM2.5)', show=False).add_to(m)
        if air_quality_data['hourly']['time']:
            last_idx = -1
            pm25 = air_quality_data['hourly']['pm2_5'][last_idx] if air_quality_data['hourly']['pm2_5'] else None
            aq_time = air_quality_data['hourly']['time'][last_idx]
            if pm25 is not None:
                color = 'green' if pm25 < 15 else 'orange' if pm25 < 50 else 'red' if pm25 < 100 else 'purple'
                folium.CircleMarker(
                    location=[latitude, longitude],
                    radius=8,
                    popup=f"PM2.5: {pm25} µg/m³ ({aq_time})",
                    color=color,
                    fill=True,
                    fill_opacity=0.7,
                    tooltip="Qualidade do Ar (PM2.5)"
                ).add_to(aq_layer)

    # Adicionar controles de camadas para o usuário poder alternar
    folium.LayerControl().add_to(m)

    plugins.Fullscreen(position='topright').add_to(m)
    plugins.MiniMap(position='bottomright').add_to(m)
    return m

def generate_pdf_report(report):
    """Gera um PDF do laudo técnico usando FPDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=report['title'], ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)

    pdf.cell(200, 10, txt=f"Data do laudo: {report['date']}", ln=1)
    pdf.cell(200, 10, txt=f"Local: {report['location']['name']}, {report['location'].get('admin1', '')}", ln=1)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Eventos Detectados:", ln=1)
    pdf.set_font("Arial", size=12)

    for event in report['events']:
        pdf.cell(200, 10, txt=f"Data: {event['date']}", ln=1)
        for e in event['events']:
            pdf.multi_cell(0, 10, txt=f"- {e}")
        pdf.ln(2)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Análise Técnica:", ln=1)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=report['analysis'])
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Recomendações:", ln=1)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=report['recommendations'])

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf_path = temp_file.name
    pdf.output(pdf_path)

    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
    os.remove(pdf_path)

    return pdf_content

def save_report_to_db(city, event_date, report_type, pdf_content):
    """Salva o laudo no banco de dados SQLite."""
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    c.execute("INSERT INTO reports (city, date, event_date, report_type, pdf_content) VALUES (?, ?, ?, ?, ?)",
              (city, datetime.now().strftime("%Y-%m-%d"), event_date, report_type, pdf_content))
    conn.commit()
    conn.close()

def get_reports_from_db():
    """Recupera todos os laudos do banco de dados."""
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    c.execute("SELECT id, city, date, event_date, report_type FROM reports ORDER BY created_at DESC")
    reports = c.fetchall()
    conn.close()
    return reports

def get_pdf_from_db(report_id):
    """Recupera o conteúdo PDF de um laudo específico."""
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    c.execute("SELECT pdf_content FROM reports WHERE id=?", (report_id,))
    pdf_content = c.fetchone()[0]
    conn.close()
    return pdf_content

def generate_technical_report(event_data, city_data, satellite_images=None):
    """Gera um laudo técnico para eventos extremos."""
    report = {
        'title': f"Laudo Técnico de Evento Climático Extremo - {city_data['name']}",
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'location': city_data,
        'events': event_data,
        'satellite_images': satellite_images,
        'analysis': "Análise dos padrões climáticos observados.",
        'recommendations': "Recomendações gerais para mitigar riscos e preparar para futuros eventos."
    }
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
    report['recommendations'] = """
    - Verificar estruturas físicas quanto a danos;
    - Monitorar áreas de risco para eventos futuros;
    - Acompanhar atualizações meteorológicas de fontes oficiais;
    - Implementar planos de contingência e evacuação conforme necessário;
    - Reforçar a infraestrutura em áreas de alto risco.
    """
    return report

# --- FUNÇÕES DE EXIBIÇÃO ---
def show_current_weather(city_data, weather_data, fire_data=None, air_quality_data=None):
    """Exibe as condições climáticas atuais e um mapa interativo."""
    st.header(f"⏱️ Condições Atuais em {city_data['name']}")

    # Cartões com métricas de clima atual
    current = weather_data["current"]
    daily = weather_data["daily"]

    # Primeira linha de métricas
    cols_metrics = st.columns(3)
    cols_metrics[0].metric("🌡️ Temperatura", f"{current['temperature_2m']}°C", f"Sensação: {current['apparent_temperature']}°C")
    cols_metrics[1].metric("💧 Umidade", f"{current['relative_humidity_2m']}%")
    cols_metrics[2].metric("🌬️ Vento", f"{current['wind_speed_10m']} km/h", f"Dir: {current['wind_direction_10m']}°")

    # Segunda linha de métricas
    cols_metrics_2 = st.columns(3)
    cols_metrics_2[0].metric("🌧️ Precipitação (1h)", f"{current['precipitation']} mm")
    cols_metrics_2[1].metric("📌 Condição", WEATHER_CODES.get(current['weather_code'], "Desconhecido"))
    uv_index = current.get('uv_index')
    cols_metrics_2[2].metric("☀️ Índice UV", f"{uv_index}" if uv_index is not None else "N/A")

    st.subheader("Informações Diárias para Hoje")
    # Cartões de informações diárias
    if daily and daily['time']:
        today_idx = 0
        cols_daily = st.columns(3)
        cols_daily[0].metric("☀️ Nascer do Sol", datetime.fromisoformat(daily['sunrise'][today_idx]).strftime("%H:%M"))
        cols_daily[1].metric("🌙 Pôr do Sol", datetime.fromisoformat(daily['sunset'][today_idx]).strftime("%H:%M"))
        cols_daily[2].metric("💧 Precipitação (24h)", f"{daily['precipitation_sum'][today_idx]} mm")

    # Mapa na parte inferior, ocupando a largura total
    st.markdown("---") # Separador visual para o mapa
    st.subheader("🌍 Mapa Interativo da Região")
    m = create_weather_map(
        city_data["latitude"],
        city_data["longitude"],
        city_data["name"],
        weather_data=weather_data,
        fire_data=fire_data,
        air_quality_data=air_quality_data
    )
    # Ajuste o width para None para que o mapa ocupe a largura total disponível
    map_data = st_folium(m, width=None, height=500, key=f"map_{city_data['name']}")

    if map_data.get("last_clicked"):
        st.session_state['map_click'] = {
            "lat": map_data["last_clicked"]["lat"],
            "lon": map_data["last_clicked"]["lng"]
        }


def show_weekly_forecast(city_data, weather_data):
    """Exibe a previsão do tempo para os próximos 7 dias."""
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
            "Índice UV Máx": daily.get("uv_index_max", [None]*len(dates)),
            "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
        }).head(7)

        fig_temp = px.line(df, x="Data", y=["Máxima (°C)", "Mínima (°C)"],
                           title="Temperaturas Diárias",
                           labels={"value": "Temperatura (°C)", "variable": "Tipo de Temperatura"},
                           line_shape="spline",
                           color_discrete_map={"Máxima (°C)": "#FF5733", "Mínima (°C)": "#3366FF"})
        fig_temp.update_layout(hovermode="x unified", legend_title_text="")
        st.plotly_chart(fig_temp, use_container_width=True)

        fig_precip = px.bar(df, x="Data", y="Precipitação (mm)",
                            title="Precipitação Diária",
                            labels={"Precipitação (mm)": "Volume (mm)"},
                            color_discrete_sequence=["#00BFFF"])
        st.plotly_chart(fig_precip, use_container_width=True)

        st.write("### Detalhes da Previsão")
        st.dataframe(df.style.background_gradient(cmap='coolwarm', subset=["Precipitação (mm)", "Vento (km/h)"]))

        upcoming_events = detect_extreme_events({"daily": {k: v[:7] for k, v in daily.items()}})
        if upcoming_events:
            st.warning("⚠️ Alertas para os próximos dias:")
            for event in upcoming_events:
                st.write(f"- **{event['date']}**: {', '.join(event['events'])}")

def show_extended_forecast(city_data, weather_data):
    """Exibe a previsão do tempo estendida (até 16 dias)."""
    st.header(f"📊 Previsão Estendida para 16 Dias em {city_data['name']}")
    st.info("Esta é a previsão máxima disponível na API Open-Meteo")

    if "daily" in weather_data:
        daily = weather_data["daily"]
        dates = pd.to_datetime(daily["time"])

        st.write(f"**A API retornou dados para {len(dates)} dias.**")

        df = pd.DataFrame({
            "Data": dates,
            "Máxima (°C)": daily["temperature_2m_max"],
            "Mínima (°C)": daily["temperature_2m_min"],
            "Precipitação (mm)": daily["precipitation_sum"],
            "Vento Máx (km/h)": daily["wind_speed_10m_max"],
            "Direção Vento": daily["wind_direction_10m_dominant"],
            "Índice UV Máx": daily.get("uv_index_max", [None]*len(dates)),
            "Condição": [WEATHER_CODES.get(code, "Desconhecido") for code in daily["weather_code"]]
        })

        tab1, tab2, tab3, tab4 = st.tabs(["Temperaturas", "Precipitação", "Ventos", "UV e Condição"])

        with tab1:
            fig_temp_ext = px.line(df, x="Data", y=["Máxima (°C)", "Mínima (°C)"],
                                   title="Temperaturas (Até 16 Dias)", line_shape="spline")
            st.plotly_chart(fig_temp_ext, use_container_width=True)

        with tab2:
            fig_precip_ext = px.bar(df, x="Data", y="Precipitação (mm)",
                                    title="Precipitação Acumulada (Até 16 Dias)")
            st.plotly_chart(fig_precip_ext, use_container_width=True)

        with tab3:
            fig_wind_ext = px.bar(df, x="Data", y="Vento Máx (km/h)",
                                  title="Velocidade Máxima do Vento (Até 16 Dias)")
            st.plotly_chart(fig_wind_ext, use_container_width=True)

        with tab4:
            st.write("### Índice UV Máximo e Condições Diárias")
            uv_df = df.set_index("Data")[["Índice UV Máx", "Condição"]]
            st.dataframe(uv_df)


def show_extreme_events(city_data, weather_data):
    """Monitora e exibe eventos climáticos extremos históricos."""
    st.header("⚠️ Monitoramento de Eventos Extremos")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    with st.spinner("Analisando dados históricos..."):
        historical_data = get_historical_weather_data(
            city_data["latitude"], city_data["longitude"], start_date, end_date
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

                    event_map = create_weather_map(
                        city_data["latitude"], city_data["longitude"], city_data["name"],
                        weather_data=None, fire_data=None, air_quality_data=None
                    )
                    folium.Marker(
                        location=[city_data["latitude"], city_data["longitude"]],
                        popup=f"Evento extremo em {event['date']}",
                        icon=folium.Icon(color='black', icon='exclamation-triangle', prefix='fa')
                    ).add_to(event_map)
                    folium_static(event_map, width=700, height=400)

                    satellite_img = get_satellite_images(city_data["latitude"], city_data["longitude"], event['date'])
                    st.image(satellite_img['image_url'],
                             caption=f"🌍 Imagem de satélite aproximada - {satellite_img['source']} ({event['date']})")

                    if st.button(f"📝 Gerar Laudo Técnico para {event['date']}",
                                 key=f"report_{event['date']}",
                                 type="primary",
                                 help="Clique para gerar um laudo técnico detalhado deste evento"):
                        report = generate_technical_report([event], city_data, [satellite_img])
                        pdf_content = generate_pdf_report(report)

                        save_report_to_db(city_data['name'], event['date'], "Evento Extremo", pdf_content)

                        st.success("Laudo técnico gerado e armazenado com sucesso!")

                        st.subheader("📄 Laudo Técnico")
                        st.write(f"**Local:** {report['location']['name']}, {report['location'].get('admin1', '')}")
                        st.write(f"**Data do Evento:** {event['date']}")
                        st.write(f"**Data do Laudo:** {report['date']}")

                        st.subheader("📊 Análise Técnica")
                        st.write(report['analysis'])

                        st.subheader("🛡️ Recomendações")
                        st.write(report['recommendations'])

                        st.download_button(
                            label="⬇️ Download do Laudo (PDF)",
                            data=pdf_content,
                            file_name=f"laudo_{city_data['name']}_{event['date']}.pdf",
                            mime="application/pdf"
                        )
        else:
            st.success("✅ Nenhum evento extremo detectado nos últimos 30 dias")
    else:
        st.error("❌ Não foi possível obter dados históricos para análise")

def show_reports_section():
    """Exibe e permite o download de laudos técnicos armazenados."""
    st.header("📂 Laudos Técnicos Armazenados")
    reports = get_reports_from_db()
    if reports:
        st.write(f"Total de laudos: {len(reports)}")
        for report in reports:
            with st.expander(f"Laudo #{report[0]} - {report[1]} ({report[3]})"):
                st.write(f"**Cidade:** {report[1]}")
                st.write(f"**Data do Laudo:** {report[2]}")
                st.write(f"**Data do Evento:** {report[3]}")
                st.write(f"**Tipo:** {report[4]}")
                pdf_content = get_pdf_from_db(report[0])
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_content,
                    file_name=f"laudo_{report[0]}_{report[1]}.pdf",
                    mime="application/pdf",
                    key=f"download_{report[0]}"
                )
    else:
        st.info("Nenhum laudo técnico armazenado ainda.")

@st.cache_data(ttl=600) # Cache por 10 minutos
def get_fire_data(latitude, longitude, radius_km=100, days_back=7):
    """Obtém dados de focos de incêndio próximos à localização."""
    try:
        delta_lat = radius_km / 111.32
        delta_lon = radius_km / (111.32 * abs(math.cos(math.radians(latitude)))) if latitude != 0 else delta_lat

        min_lat = latitude - delta_lat
        max_lat = latitude + delta_lat
        min_lon = longitude - delta_lon
        max_lon = longitude + delta_lon

        area = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        url = NASA_FIRMS_API.format(
            api_key=NASA_API_KEY,
            area=area,
            date=date
        )

        response = requests.get(url)
        response.raise_for_status()

        if response.text.strip():
            df = pd.read_csv(StringIO(response.text))
            df.rename(columns={'latitude': 'latitude', 'longitude': 'longitude', 'acq_date': 'acq_date', 'confidence': 'confidence'}, inplace=True)
            return df
        return pd.DataFrame()

    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados de focos de incêndio: {str(e)}. Verifique sua NASA_API_KEY e acesso à internet.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro inesperado ao processar dados de incêndio: {str(e)}")
        return pd.DataFrame()

def show_fire_data(city_data):
    """Exibe informações e mapa de focos de incêndio."""
    st.header("🔥 Monitoramento de Focos de Incêndio")
    st.info("Mostra focos de incêndio dos últimos 7 dias em um raio de 100km.")

    with st.spinner("Buscando dados de focos de incêndio..."):
        fire_data = get_fire_data(city_data["latitude"], city_data["longitude"], radius_km=100)

    if fire_data.empty:
        st.success("✅ Nenhum foco de incêndio detectado nos últimos 7 dias na área.")
        return

    st.warning(f"⚠️ Foram detectados {len(fire_data)} focos de incêndio próximos nos últimos 7 dias!")

    columns_to_display = ['latitude', 'longitude', 'acq_date', 'confidence']
    filtered_fire_data = fire_data[[col for col in columns_to_display if col in fire_data.columns]]
    st.dataframe(filtered_fire_data.rename(columns={
        'acq_date': 'Data Aquisição',
        'confidence': 'Confiança (%)'
    }))

    st.subheader("🌍 Mapa de Focos de Incêndio")
    fire_map = create_weather_map(
        city_data["latitude"], city_data["longitude"], city_data["name"],
        fire_data=fire_data, weather_data=None, air_quality_data=None
    )
    folium_static(fire_map, width=700, height=500)


def show_air_quality_data(city_data):
    """Exibe dados de qualidade do ar."""
    st.header("🌬️ Qualidade do Ar")
    aq_data = get_air_quality_data(city_data["latitude"], city_data["longitude"])

    if aq_data and aq_data.get('hourly'):
        hourly_aq = aq_data['hourly']
        aq_df = pd.DataFrame({
            "Hora": pd.to_datetime(hourly_aq['time']),
            "PM10 (µg/m³)": hourly_aq.get('pm10'),
            "PM2.5 (µg/m³)": hourly_aq.get('pm2_5'),
            "Monóxido de Carbono (µg/m³)": hourly_aq.get('carbon_monoxide'),
            "Dióxido de Nitrogênio (µg/m³)": hourly_aq.get('nitrogen_dioxide'),
            "Dióxido de Enxofre (µg/m³)": hourly_aq.get('sulphur_dioxide'),
            "Ozônio (µg/m³)": hourly_aq.get('ozone')
        })

        st.subheader("Principais Poluentes (Últimas Horas)")
        st.dataframe(aq_df.tail(24).set_index("Hora"))

        if not aq_df.empty:
            fig_pm = px.line(aq_df, x="Hora", y=["PM2.5 (µg/m³)", "PM10 (µg/m³)"],
                             title="Partículas em Suspensão (PM2.5 e PM10)",
                             labels={"value": "Concentração (µg/m³)", "variable": "Poluente"})
            fig_pm.update_layout(hovermode="x unified")
            st.plotly_chart(fig_pm, use_container_width=True)

            fig_gases = px.line(aq_df, x="Hora", y=["Monóxido de Carbono (µg/m³)", "Dióxido de Nitrogênio (µg/m³)", "Ozônio (µg/m³)"],
                                title="Gases Poluentes",
                                labels={"value": "Concentração (µg/m³)", "variable": "Gás"})
            fig_gases.update_layout(hovermode="x unified")
            st.plotly_chart(fig_gases, use_container_width=True)
    else:
        st.info("Nenhum dado de qualidade do ar disponível para esta localização.")


# Interface principal
def main():
    init_db()

    # Barra lateral
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-title">WeatherPro</div>
        """, unsafe_allow_html=True)

        st.markdown("### Indicação de Serviços Profissionais")
        st.markdown("""
        - **Monitoramento** de eventos extremos
        - **Laudos técnicos** personalizados
        - **Alertas** em tempo real
        - **API** para integração corporativa
        """)

        st.markdown("### Planos Disponíveis")
        st.markdown("""
        - **Básico**: Previsões padrão
        - **Profissional**: Eventos extremos
        - **Corporativo**: Laudos + API
        """)

        st.markdown("---")
        st.markdown("📞 **Contato:** contato@weatherpro.com")
        st.markdown("🌐 [www.weatherpro.com](https://www.weatherpro.com)")

        if st.button("📂 Ver Laudos Armazenados", key="view_reports_sidebar"):
            st.session_state.show_stored_reports = True
        else:
            st.session_state.show_stored_reports = False

    # Seção de pesquisa com localização automática
    st.write("### 🌍 Pesquisar por Localização")

    if 'current_city_search' not in st.session_state:
        st.session_state.current_city_search = ""
    if 'current_city_display' not in st.session_state:
        st.session_state.current_city_display = ""
    if 'current_location_coords' not in st.session_state:
        st.session_state.current_location_coords = None
    if 'trigger_geolocation' not in st.session_state:
        st.session_state.trigger_geolocation = False


    col1, col2 = st.columns([3, 1])

    with col1:
        city_name_input = st.text_input("Digite o nome da cidade:",
                                       value=st.session_state.current_city_search,
                                       key="city_search_input",
                                       placeholder="Ex: São Paulo, Rio de Janeiro")

    with col2:
        st.write("")
        st.write("")
        if st.button("📍 Usar Minha Localização",
                     help="Clique e permita o acesso à localização no seu navegador",
                     key="get_location_button"):
            st.session_state.trigger_geolocation = True
            st.session_state.current_city_search = ""
            st.session_state.current_city_display = ""
            st.session_state.current_location_coords = None


    # Componente de geolocalização (JavaScript)
    geolocation_script = f"""
    <script>
    const streamlitAppReady = typeof Streamlit !== 'undefined';
    const triggerGeolocation = {str(st.session_state.get('trigger_geolocation', False)).lower()};

    if (streamlitAppReady && triggerGeolocation) {{
        Streamlit.setComponentValue('trigger_geolocation', false);

        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    const message = `Minha Localização,${{lat}},${{lon}}`;
                    Streamlit.setComponentValue('user_location_result', message);
                }},
                function(error) {{
                    let errorMessage;
                    switch(error.code) {{
                        case error.PERMISSION_DENIED:
                            errorMessage = "Acesso à localização negado pelo usuário. Por favor, permita no navegador.";
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = "Informações de localização não disponíveis.";
                            break;
                        case error.TIMEOUT:
                            errorMessage = "Tempo limite para obter localização excedido.";
                            break;
                        default:
                            errorMessage = "Erro desconhecido ao obter localização.";
                    }}
                    Streamlit.setComponentValue('location_error_message', errorMessage);
                }},
                {{enableHighAccuracy: true, timeout: 10000, maximumAge: 0}}
            );
        }} else {{
            Streamlit.setComponentValue('location_error_message', "Geolocalização não é suportada por este navegador.");
        }}
    }}
    </script>
    """
    st.components.v1.html(geolocation_script, height=0)


    # Processar resposta da geolocalização
    if st.session_state.get('user_location_result'):
        parts = st.session_state.user_location_result.split(',')
        lat = float(parts[1])
        lon = float(parts[2])

        try:
            geo_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
            geo_response = requests.get(geo_url)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            if geo_data and geo_data.get('address'):
                address = geo_data['address']
                city_name_from_coords = address.get('city') or address.get('town') or address.get('village') or geo_data.get('display_name', "Minha Localização")
                state = address.get('state', '')
                country = address.get('country', '')
                st.session_state.current_city_display = f"{city_name_from_coords}, {state}, {country}"
            else:
                st.session_state.current_city_display = f"Localização Detectada (Lat: {lat:.2f}, Lon: {lon:.2f})"

        except requests.exceptions.RequestException:
            st.session_state.current_city_display = f"Localização Detectada (Lat: {lat:.2f}, Lon: {lon:.2f})"
        except Exception:
            st.session_state.current_city_display = f"Localização Detectada (Lat: {lat:.2f}, Lon: {lon:.2f})"

        st.session_state.current_location_coords = {"lat": lat, "lon": lon}
        st.session_state.current_city_search = st.session_state.current_city_display
        st.session_state.pop('user_location_result')


    if st.session_state.get('location_error_message'):
        st.warning(st.session_state.location_error_message)
        st.session_state.pop('location_error_message')


    selected_city_data = None
    if st.session_state.get('current_location_coords') and not city_name_input:
        selected_city_data = {
            "name": st.session_state.get('current_city_display', "Minha Localização"),
            "latitude": st.session_state.current_location_coords["lat"],
            "longitude": st.session_state.current_location_coords["lon"],
            "admin1": "", "country": ""
        }
        st.info(f"Mostrando clima para: **{selected_city_data['name']}**")
    elif city_name_input:
        city_options = get_city_options(city_name_input)
        if city_options:
            options_display = [f"{city['name']}, {city.get('admin1', '')}, {city.get('country', '')} (Lat: {city['latitude']:.2f}, Lon: {city['longitude']:.2f})" for city in city_options]
            selected_option = st.selectbox(
                "📍 Selecione a localidade correta:",
                options_display,
                key="city_selection_box",
                index=0
            )
            selected_index = options_display.index(selected_option)
            selected_city_data = city_options[selected_index]
            st.session_state.current_location_coords = None
            st.session_state.current_city_display = ""
        else:
            st.warning("Nenhuma cidade encontrada com esse nome. Tente novamente ou use a localização automática.")

    if selected_city_data:
        weather_data = get_weather_data(
            selected_city_data["latitude"],
            selected_city_data["longitude"],
            selected_city_data.get("timezone", "auto")
        )
        fire_data = get_fire_data(
            selected_city_data["latitude"],
            selected_city_data["longitude"],
            radius_km=100
        )
        air_quality_data = get_air_quality_data(
            selected_city_data["latitude"],
            selected_city_data["longitude"]
        )

        if weather_data:
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "⏱️ Atual", "📅 7 Dias", "📊 16 Dias",
                "⚠️ Eventos Extremos", "🔥 Focos de Incêndio", "🌬️ Qualidade do Ar"
            ])

            with tab1:
                show_current_weather(selected_city_data, weather_data, fire_data, air_quality_data)

            with tab2:
                show_weekly_forecast(selected_city_data, weather_data)

            with tab3:
                show_extended_forecast(selected_city_data, weather_data)

            with tab4:
                show_extreme_events(selected_city_data, weather_data)

            with tab5:
                show_fire_data(selected_city_data)

            with tab6:
                show_air_quality_data(selected_city_data)
        else:
            st.error("Não foi possível obter dados de clima para a localização selecionada.")
    elif st.session_state.get('show_stored_reports'):
        show_reports_section()
    else:
        st.info("Por favor, digite uma cidade ou use sua localização para começar.")

if __name__ == "__main__":
    main()

st.markdown("---")
st.markdown("""
<div class="footer">
App desenvolvido com Python, Streamlit e Open-Meteo | WeatherPro - Soluções em Monitoramento Climático Corporativo | © 2025
</div>
""", unsafe_allow_html=True)
