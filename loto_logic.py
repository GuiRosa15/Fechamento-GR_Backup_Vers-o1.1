import random
from itertools import combinations

# Regras da Lotofácil
TOTAL_NUMEROS = 25
MIN_APOSTA = 15
MAX_APOSTA = 20

def validar_volante(numeros):
    """Verifica se os números escolhidos são válidos."""
    if len(numeros) != len(set(numeros)):
        return False, "Existem números repetidos."
    
    for n in numeros:
        if n < 1 or n > 25:
            return False, f"O número {n} é inválido. Escolha entre 1 e 25."
            
    return True, "Números válidos."

def gerar_fechamento(total_numeros_jogados, numeros_fixos, completar_aleatorio=False):
    """
    Gera jogos baseados em fechamento simples (combinatória).
    
    :param total_numeros_jogados: Quantos números queremos cercar (ex: 17, 18).
    :param numeros_fixos: Lista de números que devem aparecer em todos os jogos.
    :param completar_aleatorio: Se True, o sistema escolhe o restante dos números.
    """
    
    # Validações básicas
    if len(numeros_fixos) > 15:
        return {"erro": "Você não pode fixar mais de 15 números."}
    
    if total_numeros_jogados < 15 or total_numeros_jogados > 20:
        return {"erro": "A aposta deve ter entre 15 e 20 números."}

    # Se o usuário quiser gerar aleatório (sem escolher números)
    numeros_para_escolher = []
    
    if completar_aleatorio:
        # Pega números que NÃO são fixos para preencher
        disponiveis = [n for n in range(1, 26) if n not in numeros_fixos]
        # Quantos faltam para chegar no total desejado
        qtd_faltante = total_numeros_jogados - len(numeros_fixos)
        numeros_aleatorios = random.sample(disponiveis, qtd_faltante)
        numeros_para_escolher = numeros_aleatorios
    else:
        # Aqui assumimos que o usuário passaria o restante, 
        # mas para este exemplo, vamos focar na lógica de gerar os jogos finais
        pass

    # LÓGICA DO FECHAMENTO MATEMÁTICO
    # Exemplo: O usuário quer jogar com 17 números no total.
    # Ele fixou 13 números. Faltam 2 vagas em cada jogo de 15.
    # Mas ele escolheu mais 4 números variáveis para rodar nessas 2 vagas.
    
    # Para simplificar este primeiro passo, faremos um gerador de combinações puras
    # Se o usuário escolheu um 'pool' de 18 números, vamos gerar todas as combinações
    # possíveis de 15 números dentro desse pool.
    
    # NOTA: Em um app real, o usuário fornece o 'pool' completo (fixos + variáveis).
    # Abaixo, simulo um pool para teste se não for fornecido.
    
    pool = numeros_fixos + numeros_para_escolher
    pool = sorted(list(set(pool))) # Remove duplicatas e ordena
    
    jogos_gerados = []
    
    # Fórmula de Combinação: C(n, k) -> Combinar 'pool' em grupos de 15
    # Cuidado: Se o pool for muito grande (ex: 25), gera milhões de jogos.
    # Limitamos ao tamanho do 'pool' escolhido pelo usuário.
    
    if len(pool) < 15:
        return {"erro": f"Faltam números. Você tem apenas {len(pool)} selecionados."}
    
    # Gera todas as combinações de 15 números possíveis dentro do pool escolhido
    comb = combinations(pool, 15)
    
    for c in comb:
        jogos_gerados.append(list(c))
        
        # Limite de segurança para não travar o servidor em testes
        if len(jogos_gerados) > 1000:
            break
            
    return {
        "total_jogos": len(jogos_gerados),
        "numeros_base": pool,
        "jogos": jogos_gerados
    }

# --- TESTE RÁPIDO NO CONSOLE ---
if __name__ == "__main__":
    print("--- Teste Fechamento do GR ---")
    # Usuário quer cercar 17 números, fixando 13 deles.
    meus_fixos = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    resultado = gerar_fechamento(total_numeros_jogados=17, numeros_fixos=meus_fixos, completar_aleatorio=True)
    
    if "erro" in resultado:
        print(resultado["erro"])
    else:
        print(f"Números Base ({len(resultado['numeros_base'])}): {resultado['numeros_base']}")
        print(f"Total de jogos gerados de 15 números: {resultado['total_jogos']}")
        print("Exemplo dos 5 primeiros jogos:")
        for jogo in resultado['jogos'][:5]:
            print(jogo)