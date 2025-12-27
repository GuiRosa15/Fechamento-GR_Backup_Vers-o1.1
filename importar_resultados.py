import requests
import time
from app import app, db, ResultadoLotofacil

# URL da API Gratuita (Loterias API)
URL_BASE = "https://loteriascaixa-api.herokuapp.com/api/lotofacil"

def importar_jogos(quantidade=50):
    print(f"🤖 Iniciando o robô... Buscando os últimos {quantidade} resultados.")
    
    with app.app_context():
        # 1. Descobre qual é o último concurso disponível na API
        try:
            resp = requests.get(URL_BASE, timeout=10)
            if resp.status_code != 200:
                print("❌ Erro ao conectar na API. Tente mais tarde.")
                return
            
            dados_recente = resp.json()
            ultimo_concurso = int(dados_recente['concurso'])
            print(f"🔥 Último concurso oficial: {ultimo_concurso}")
            
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
            return

        # 2. Faz um loop do último para trás (para pegar os anteriores)
        contador = 0
        for i in range(ultimo_concurso, ultimo_concurso - quantidade, -1):
            
            # Verifica se já temos esse concurso no banco (para não duplicar)
            existe = ResultadoLotofacil.query.filter_by(concurso=i).first()
            if existe:
                print(f"✅ Concurso {i} já existe no banco. Pulando...")
                continue

            # Se não existe, busca na API
            print(f"🔄 Baixando concurso {i}...")
            try:
                # Chama a API específica do concurso
                r = requests.get(f"{URL_BASE}/{i}", timeout=5)
                if r.status_code == 200:
                    dados = r.json()
                    
                    # Formata as dezenas (Vêm como lista, transformamos em string "01, 02...")
                    lista_dezenas = [int(d) for d in dados['dezenas']]
                    dezenas_str = ", ".join([f"{n:02d}" for n in sorted(lista_dezenas)])
                    
                    # Salva no Banco
                    novo_res = ResultadoLotofacil(
                        concurso=dados['concurso'],
                        data_sorteio=dados['data'],
                        dezenas=dezenas_str
                    )
                    db.session.add(novo_res)
                    db.session.commit()
                    contador += 1
                    
                    # Pausa de 1 segundo para não bloquear a API (importante!)
                    time.sleep(1)
                else:
                    print(f"⚠️ Erro ao baixar concurso {i}")
            
            except Exception as e:
                print(f"❌ Erro no concurso {i}: {e}")

        print(f"\n🎉 Pronto! {contador} novos resultados importados com sucesso.")

# Executa a função
if __name__ == "__main__":
    # Você pode mudar o número 50 para 100, 200, etc.
    importar_jogos(quantidade=50)