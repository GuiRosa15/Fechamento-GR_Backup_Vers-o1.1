import google.generativeai as genai

# Cole sua chave aqui para testar
genai.configure(api_key="AIzaSyDIZph__BBc9NvxkIFrH2OjMMM1OoABNrs")

print("Listando modelos disponíveis para você...")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")