import streamlit as st
import requests
import pandas as pd
from io import StringIO
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import sqlite3
from folium import plugins
import tempfile
from fpdf import FPDF
import os

# Configurações para API de focos de incêndio
NASA_FIRMS_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_NOAA20_NRT/{area}/1/{date}"
NASA_API_KEY = "DEMO_KEY"  # Chave demo - para produção, registre-se e obtenha uma chave em https://earthdata.nasa.gov/

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
            event['events'].append(f"Precipitação extrema: {precip_value} mm")
        
        # Verificar ventos fortes
        wind_value = daily_data.get('wind_speed_10m_max', [0]*len(dates))[i] or 0
        if wind_value > threshold['wind_speed']:
            direction = daily_data.get('wind_direction_10m_dominant', [0]*len(dates))[i]
            event['events'].append(f"Rajada de vento: {wind_value} km/h, direção {direction}°")
        
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

def create_weather_map(latitude, longitude, city_name, weather_data=None, fire_data=None):
    """Cria um mapa meteorológico interativo similar ao WeatherPro"""
    m = folium.Map(
        location=[latitude, longitude],
        zoom_start=10,
        tiles='https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
        attr='OpenStreetMap.HOT',
        control_scale=True,
        prefer_canvas=True
    )
    
    # Adicionar marcador da cidade
    folium.Marker(
        location=[latitude, longitude],
        popup=f"<b>{city_name}</b><br>Estamos aqui",
        tooltip=city_name,
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    # Adicionar camada de focos de incêndio se existirem dados
    if fire_data is not None and not fire_data.empty:
        fire_layer = folium.FeatureGroup(name='Focos de Incêndio (últimos 7 dias)')
        
        for _, row in fire_data.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=3,
                popup=f"Foco em {row['acq_date']}<br>Confiança: {row['confidence']}%",
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(fire_layer)
        
        fire_layer.add_to(m)
    
    if weather_data and 'hourly' in weather_data:
        temperature_layer = folium.FeatureGroup(name='Temperatura')
        
        for i in range(0, len(weather_data['hourly']['time']), 6):
            temp = weather_data['hourly']['temperature_2m'][i]
            time = weather_data['hourly']['time'][i]
            
            # Verificação para garantir que temp é um número válido
            if temp is None:
                continue
                
            try:
                temp = float(temp)
                color = 'blue' if temp < 10 else 'green' if temp < 20 else 'orange' if temp < 30 else 'red'
                
                folium.CircleMarker(
                    location=[latitude + 0.1 * (i % 3 - 1), longitude + 0.1 * (i % 4 - 2)],
                    radius=5 + temp/5,
                    popup=f"Temp: {temp}°C<br>Hora: {time}",
                    color=color,
                    fill=True,
                    fill_color=color
                ).add_to(temperature_layer)
            except (TypeError, ValueError):
                continue
        
        temperature_layer.add_to(m)
    
    precipitation_layer = folium.FeatureGroup(name='Precipitação')
    if weather_data and 'daily' in weather_data:
        for i, precip in enumerate(weather_data['daily']['precipitation_sum']):
            if precip is None:
                continue
                
            try:
                precip = float(precip)
                if precip > 0:
                    folium.Circle(
                        location=[latitude + 0.05 * i, longitude - 0.05 * i],
                        radius=precip * 100,
                        popup=f"Precipitação: {precip}mm",
                        color='blue',
                        fill=True,
                        fill_opacity=0.2
                    ).add_to(precipitation_layer)
            except (TypeError, ValueError):
                continue
    precipitation_layer.add_to(m)
    
    folium.LayerControl().add_to(m)
    
    plugins.Fullscreen(
        position='topright',
        title='Expandir mapa',
        title_cancel='Sair do modo tela cheia',
        force_separate_button=True
    ).add_to(m)
    
    plugins.MiniMap(tile_layer='OpenStreetMap', position='bottomright').add_to(m)
    
    plugins.LocateControl(
        auto_start=False,
        position='topright',
        draw_circle=True,
        fly_to=True,
        keep_current_zoom_level=True,
        locate_options={'enableHighAccuracy': True}
    ).add_to(m)
    
    return m

def generate_pdf_report(report):
    """Gera um PDF do laudo técnico usando FPDF"""
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
    
    return pdf_content

def save_report_to_db(city, event_date, report_type, pdf_content):
    """Salva o laudo no banco de dados SQLite"""
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    
    c.execute("INSERT INTO reports (city, date, event_date, report_type, pdf_content) VALUES (?, ?, ?, ?, ?)",
              (city, datetime.now().strftime("%Y-%m-%d"), event_date, report_type, pdf_content))
    
    conn.commit()
    conn.close()

def get_reports_from_db():
    """Recupera todos os laudos do banco de dados"""
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    
    c.execute("SELECT id, city, date, event_date, report_type FROM reports ORDER BY created_at DESC")
    reports = c.fetchall()
    
    conn.close()
    return reports

def get_pdf_from_db(report_id):
    """Recupera o conteúdo PDF de um laudo específico"""
    conn = sqlite3.connect('weather_reports.db')
    c = conn.cursor()
    
    c.execute("SELECT pdf_content FROM reports WHERE id=?", (report_id,))
    pdf_content = c.fetchone()[0]
    
    conn.close()
    return pdf_content

def generate_technical_report(event_data, city_data, satellite_images=None):
    """Gera um laudo técnico para eventos extremos"""
    report = {
        'title': f"Laudo Técnico de Evento Climático Extremo - {city_data['name']}",
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'location': city_data,
        'events': event_data,
        'satellite_images': satellite_images,
        'analysis': "",
        'recommendations': ""
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
    - Verificar estruturas físicas quanto a danos
    - Monitorar áreas de risco para eventos futuros
    - Acompanhar atualizações meteorológicas
    - Implementar planos de contingência conforme necessário
    """
    
    return report

# Funções de exibição
def show_current_weather(city_data, weather_data):
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
        m = create_weather_map(
            city_data["latitude"],
            city_data["longitude"],
            city_data["name"],
            weather_data
        )
        folium_static(m, width=400, height=400)

def show_weekly_forecast(city_data, weather_data):
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
        
        upcoming_events = detect_extreme_events({
            "daily": {k: v[:7] for k, v in daily.items()}
        })
        
        if upcoming_events:
            st.warning("⚠️ Alertas para os próximos dias:")
            for event in upcoming_events:
                st.write(f"- {event['date']}: {', '.join(event['events'])}")

def show_extended_forecast(city_data, weather_data):
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
    st.header("⚠️ Monitoramento de Eventos Extremos")
    
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
                    
                    satellite_img = get_satellite_images(
                        city_data["latitude"],
                        city_data["longitude"],
                        event['date']
                    )
                    
                    st.image(satellite_img['image_url'], 
                            caption=f"🌍 Imagem de satélite aproximada - {satellite_img['source']} ({event['date']})")
                    
                    if st.button(f"📝 Gerar Laudo Técnico para {event['date']}", 
                               key=f"report_{event['date']}",
                               type="primary",
                               help="Clique para gerar um laudo técnico detalhado deste evento"):
                        report = generate_technical_report([event], city_data, [satellite_img])
                        pdf_content = generate_pdf_report(report)
                        
                        save_report_to_db(
                            city_data['name'],
                            event['date'],
                            "Evento Extremo",
                            pdf_content
                        )
                        
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

def get_fire_data(latitude, longitude, radius_km=100, days_back=7):
    """Obtém dados de focos de incêndio próximos à localização"""
    try:
        # Calcular área de busca (latitude/longitude deltas)
        delta = radius_km / 111.32  # Aproximadamente 111.32 km por grau
        
        min_lat = latitude - delta
        max_lat = latitude + delta
        min_lon = longitude - delta
        max_lon = longitude + delta
        
        area = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        url = NASA_FIRMS_API.format(
            api_key=NASA_API_KEY,
            area=area,
            date=date
        )
        
        response = requests.get(url)
        response.raise_for_status()
        
        # Processar os dados se a resposta não estiver vazia
        if response.text.strip():
            df = pd.read_csv(StringIO(response.text))
            return df
        return pd.DataFrame()
    
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados de focos de incêndio: {str(e)}")
        return pd.DataFrame()

def show_fire_data(city_data):
    st.header("🔥 Monitoramento de Focos de Incêndio")
    
    with st.spinner("Buscando dados de focos de incêndio..."):
        fire_data = get_fire_data(
            city_data["latitude"],
            city_data["longitude"],
            radius_km=100  # Raio de 100km ao redor da cidade
        )
    
    if not fire_data.empty:
        st.warning(f"⚠️ Foram detectados {len(fire_data)} focos de incêndio próximos nos últimos 7 dias")
        
        # Mostrar dados em tabela
        st.dataframe(fire_data[['latitude', 'longitude', 'acq_date', 'confidence']]
                     .rename(columns={
                         'latitude': 'Latitude',
                         'longitude': 'Longitude',
                         'acq_date': 'Data',
                         'confidence': 'Confiança (%)'
                     }))
        
        # Mostrar no mapa
        st.subheader("🌍 Mapa de Focos de Incêndio")
        fire_map = create_weather_map(
            city_data["latitude"],
            city_data["longitude"],
            city_data["name"],
            fire_data=fire_data
        )
        folium_static(fire_map)
    else:
        st.success("✅ Nenhum foco de incêndio detectado nos últimos 7 dias")

# Interface principal
def main():
    init_db()
    
    # Barra lateral
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Weather+Pro", width=150)
        st.markdown("### Indicação de Serviços Profissionais - Empresa weatherpro")
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
        
        if st.sidebar.button("📂 Ver Laudos Armazenados"):
            show_reports_section()

    # Seção de pesquisa com localização automática
    st.write("### 🌍 Pesquisar por Localização")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        city_name = st.text_input("🔍 Digite o nome da cidade:", value="", key="city_search")
    
    with col2:
        if st.button("📍 Usar Minha Localização", help="Clique para usar sua localização atual"):
            try:
                # Componente para geolocalização
                st.components.v1.html("""
                <script>
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        window.parent.postMessage({
                            type: 'streamlit:setComponentValue',
                            value: position.coords.latitude + "," + position.coords.longitude
                        }, '*');
                    },
                    function(error) {
                        console.error("Error getting location: ", error);
                    }
                );
                </script>
                """, height=0)
                
                # Verificar se a localização foi recebida
                location = st.session_state.get('location', None)
                
                if location:
                    lat, lon = map(float, location.split(','))
                    city_data = {
                        "name": "Local Atual",
                        "latitude": lat,
                        "longitude": lon,
                        "admin1": "",
                        "country": ""
                    }
                    
                    weather_data = get_weather_data(lat, lon)
                    
                    if weather_data:
                        tab1, tab2, tab3, tab4, tab5 = st.tabs([
                            "⏱️ Atual", 
                            "📅 7 Dias", 
                            "📊 16 Dias",
                            "⚠️ Eventos Extremos",
                            "🔥 Focos de Incêndio"
                        ])

                        with tab1:
                            show_current_weather(city_data, weather_data)
                        
                        with tab2:
                            show_weekly_forecast(city_data, weather_data)
                        
                        with tab3:
                            show_extended_forecast(city_data, weather_data)
                        
                        with tab4:
                            show_extreme_events(city_data, weather_data)
                        
                        with tab5:
                            show_fire_data(city_data)
                    else:
                        st.error("Não foi possível obter dados para sua localização")
                else:
                    st.warning("Permissão de localização não concedida ou não disponível")
            except Exception as e:
                st.error(f"Erro ao obter localização: {str(e)}")
    
    # Seção principal apenas se uma cidade foi pesquisada
    if city_name:
        city_options = get_city_options(city_name)
        
        if city_options:
            options = [
                f"{city['name']}, {city.get('admin1', '')}, {city.get('country', '')} (Lat: {city['latitude']:.2f}, Lon: {city['longitude']:.2f})"
                for city in city_options
            ]
            
            selected_city = st.selectbox(
                "📍 Selecione a localidade correta:",
                options,
                index=0
            )
            
            selected_index = options.index(selected_city)
            city_data = city_options[selected_index]
            
            weather_data = get_weather_data(
                city_data["latitude"],
                city_data["longitude"],
                city_data.get("timezone", "auto")
            )
            
            if weather_data:
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "⏱️ Atual", 
                    "📅 7 Dias", 
                    "📊 16 Dias",
                    "⚠️ Eventos Extremos",
                    "🔥 Focos de Incêndio"
                ])
                
                with tab1:
                    show_current_weather(city_data, weather_data)
                
                with tab2:
                    show_weekly_forecast(city_data, weather_data)
                
                with tab3:
                    show_extended_forecast(city_data, weather_data)
                
                with tab4:
                    show_extreme_events(city_data, weather_data)
                
                with tab5:
                    show_fire_data(city_data)

if __name__ == "__main__":
    main()

# Rodapé
st.markdown("---")
st.markdown("App desenvolvido com Python, Streamlit e Open-Meteo e WeatherPro - Soluções em Monitoramento Climático Corporativo - API Alliabson @2025")
