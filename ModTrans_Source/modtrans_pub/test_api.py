import os
import urllib.request
import json

# Cerca entrambe le varianti del nome per sicurezza
key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPEN_ROUTER_API_KEY")

if not key:
    print("ERRORE: Python non riesce a leggere la variabile d'ambiente. Riavvia il PC o l'editor.")
    exit()

print("Chiave trovata!")

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}
data = {
    "model": "deepseek/deepseek-chat",  # Modello di test gratuito e sempre attivo
    "messages": [{"role": "user", "content": "Rispondi solo con la parola: Funziona"}]
}

try:
    print("Contattando OpenRouter...")
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read())
        print("\nSUCCESSO! Risposta dell'IA:")
        print(res["choices"][0]["message"]["content"])
except Exception as e:
    print("\nERRORE RESTITUITO DA OPENROUTER:")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
    else:
        print(str(e))