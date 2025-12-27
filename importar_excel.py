import pandas as pd
from app import app, db, ResultadoLotofacil

def importar_do_excel():
    print("📂 Lendo o arquivo 'resultados.xlsx'...")
    
    try:
        # Lê o Excel
        df = pd.read_excel('resultados.xlsx')
        
        # Garante que as colunas existem
        colunas_necessarias = ['Concurso', 'Data'] + [f'Bola{i}' for i in range(1, 16)]
        for col in colunas_necessarias:
            if col not in df.columns:
                print(f"❌ Erro: Coluna '{col}' não encontrada no Excel.")
                print("Certifique-se que o cabeçalho está: Concurso, Data, Bola1, Bola2... Bola15")
                return

        total_importado = 0
        
        with app.app_context():
            # Percorre cada linha do Excel
            for index, row in df.iterrows():
                try:
                    num_concurso = int(row['Concurso'])
                    
                    # Verifica se já existe no banco
                    if ResultadoLotofacil.query.filter_by(concurso=num_concurso).first():
                        print(f"⏩ Concurso {num_concurso} já existe. Pulando.")
                        continue
                    
                    # Pega as 15 dezenas
                    dezenas_lista = []
                    for i in range(1, 16):
                        bola = int(row[f'Bola{i}'])
                        dezenas_lista.append(bola)
                    
                    # Ordena e Formata (01, 02, 03...)
                    dezenas_lista.sort()
                    dezenas_str = ", ".join([f"{n:02d}" for n in dezenas_lista])
                    
                    # Formata a data (se vier como datetime do Excel)
                    data_str = str(row['Data'])
                    if " " in data_str: # Remove hora se tiver (2024-01-01 00:00:00 -> 2024-01-01)
                        data_str = data_str.split(" ")[0]
                        # Tenta converter para BR se estiver em formato americano
                        try:
                            partes = data_str.split("-")
                            if len(partes) == 3: # ano-mes-dia
                                data_str = f"{partes[2]}/{partes[1]}/{partes[0]}"
                        except: pass

                    # Salva
                    novo = ResultadoLotofacil(
                        concurso=num_concurso,
                        data_sorteio=data_str,
                        dezenas=dezenas_str
                    )
                    db.session.add(novo)
                    total_importado += 1
                    print(f"✅ Concurso {num_concurso} importado!")
                    
                except Exception as e:
                    print(f"⚠️ Erro na linha {index}: {e}")

            db.session.commit()
            print(f"\n🎉 Sucesso! {total_importado} novos resultados importados.")

    except FileNotFoundError:
        print("❌ Arquivo 'resultados.xlsx' não encontrado na pasta.")
    except Exception as e:
        print(f"❌ Erro grave: {e}")

if __name__ == "__main__":
    importar_do_excel()