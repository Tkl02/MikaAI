import requests

def get_weather():
        try:
            url = "https://api.open-meteo.com/v1/forecast?latitude=-17.80583&longitude=-49.61278&current_weather=true" #minha localização
            response = requests.get(url, timeout=5).json()
            temp = response.get('current_weather',{}).get('temperature','desconhecida')
            return f"Esta fazendo {temp} graus celsius"
        except Exception as e:
            return "não consegui acessar os dados meteorológicos no momento"

clima = get_weather()

print(clima)