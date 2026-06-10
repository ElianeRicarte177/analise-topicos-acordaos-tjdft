"""
Coleta de Acórdãos - TJDFT / JurisDF
======================================
Projeto: Auditoria Algorítmica do OdinGPT (corpus de ações de alimentos)
Filtros: 7ª Turma Cível | 2024-01-01 a 2025-12-31
API: POST https://jurisdf.tjdft.jus.br/api/v1/pesquisa
"""

import requests
import csv
import json
import time
import os
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
API_URL      = "https://jurisdf.tjdft.jus.br/api/v1/pesquisa"
QUERY        = "alimentos"
TAMANHO      = 20
PAUSA_SEG    = 3.0
ARQUIVO_CSV  = "acordaos_7turma_2022_2025.csv"
ARQUIVO_LOG  = "coleta_log.json"
MAX_RETRIES  = 6

# Apenas o filtro de turma — vamos filtrar por data no pós-processamento
FILTROS = [
    {"campo": "descricaoOrgaoJulgador", "valor": "7ª Turma Cível"},
]

CAMPOS_CSV = [
    "sequencial", "base", "subbase", "uuid", "identificador",
    "processo", "dataJulgamento", "dataPublicacao", "nomeRelator",
    "nomeRevisor", "descricaoOrgaoJulgador", "descricaoClasseCnj",
    "ementa", "inteiroTeor", "possuiInteiroTeor",
]

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://jurisdf.tjdft.jus.br",
    "Referer": "https://jurisdf.tjdft.jus.br/",
}

# Filtro de data aplicado em Python (pós-coleta por página)
DATA_INICIO = "2022-01-01"
DATA_FIM    = "2025-12-31"


# ─────────────────────────────────────────────
# FUNÇÕES
# ─────────────────────────────────────────────

def buscar_pagina_com_retry(query, pagina, tamanho, filtros):
    pausa_atual = PAUSA_SEG
    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                API_URL,
                json={
                    "query": query,
                    "pagina": pagina,
                    "tamanho": tamanho,
                    "termosAcessorios": filtros,
                },
                headers=HEADERS,
                timeout=30
            )
            if resp.status_code == 429:
                espera = pausa_atual * (2 ** tentativa)
                print(f"    [429] Muitas requisições. Aguardando {espera:.0f}s (tentativa {tentativa}/{MAX_RETRIES})...")
                time.sleep(espera)
                continue
            if resp.status_code == 500:
                espera = pausa_atual * (2 ** tentativa)
                print(f"    [500] Erro no servidor. Aguardando {espera:.0f}s (tentativa {tentativa}/{MAX_RETRIES})...")
                time.sleep(espera)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            espera = pausa_atual * tentativa
            print(f"    [TIMEOUT] Aguardando {espera:.0f}s (tentativa {tentativa}/{MAX_RETRIES})...")
            time.sleep(espera)
        except requests.exceptions.RequestException as e:
            espera = pausa_atual * tentativa
            print(f"    [ERRO] {e} — Aguardando {espera:.0f}s (tentativa {tentativa}/{MAX_RETRIES})...")
            time.sleep(espera)
    return None


def dentro_do_periodo(registro, data_inicio, data_fim):
    """Verifica se o registro está dentro do período desejado."""
    data_raw = registro.get("dataJulgamento", "") or registro.get("dataPublicacao", "")
    if not data_raw:
        return True  # sem data, inclui por segurança
    data = data_raw[:10]  # pega só YYYY-MM-DD
    return data_inicio <= data <= data_fim


def extrair_campos(registro):
    row = {}
    for campo in CAMPOS_CSV:
        valor = registro.get(campo, "")
        if isinstance(valor, str):
            valor = valor.replace("\n", " ").replace("\r", " ").strip()
        row[campo] = valor
    return row


def salvar_csv(registros, arquivo, modo="a"):
    escrever_header = not os.path.exists(arquivo) or modo == "w"
    with open(arquivo, mode=modo, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        if escrever_header:
            writer.writeheader()
        writer.writerows(registros)


def contar_linhas_csv(arquivo):
    if not os.path.exists(arquivo):
        return 0
    with open(arquivo, encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


def pagina_inicial_pelo_csv(arquivo, tamanho):
    linhas = contar_linhas_csv(arquivo)
    if linhas == 0:
        return 0
    pagina = linhas // tamanho
    print(f"  CSV existente com {linhas:,} registros → retomando da página {pagina}")
    return pagina


# ─────────────────────────────────────────────
# EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Coleta de Acórdãos — TJDFT / JurisDF")
    print("=" * 60)
    print(f"  Query     : {QUERY}")
    print(f"  Turma     : 7ª Turma Cível")
    print(f"  Período   : {DATA_INICIO} a {DATA_FIM} (filtro local)")
    print(f"  Arquivo   : {ARQUIVO_CSV}")
    print(f"  Iniciando : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n[1] Consultando total de resultados...")
    dados = buscar_pagina_com_retry(QUERY, pagina=0, tamanho=TAMANHO, filtros=FILTROS)
    if dados is None:
        print("  ERRO: não foi possível conectar à API.")
        return

    hits_raw = dados.get("hits", 0)
    total = hits_raw.get("value", 0) if isinstance(hits_raw, dict) else int(hits_raw)
    total_paginas = (total + TAMANHO - 1) // TAMANHO

    print(f"  Total de acórdãos (7ª Turma) : {total:,}")
    print(f"  Total de páginas             : {total_paginas:,}")
    print(f"  (Filtro de 2024-2025 aplicado localmente)")

    if total == 0:
        print("\n  Nenhum resultado.")
        return

    pagina_inicio = pagina_inicial_pelo_csv(ARQUIVO_CSV, TAMANHO)
    coletados = contar_linhas_csv(ARQUIVO_CSV)

    if pagina_inicio == 0:
        print(f"\n  Iniciando coleta do zero.")
        confirmacao = input("  Continuar? (s/n): ").strip().lower()
        if confirmacao != "s":
            print("  Cancelado.")
            return
        registros_filtrados = [
            extrair_campos(r) for r in dados.get("registros", [])
            if dentro_do_periodo(r, DATA_INICIO, DATA_FIM)
        ]
        salvar_csv(registros_filtrados, ARQUIVO_CSV, modo="w")
        coletados = len(registros_filtrados)
        print(f"\n  Página   0/{total_paginas-1} — {coletados:,} registros salvos")
        inicio_loop = 1
    else:
        print(f"  Retomando da página {pagina_inicio} ({coletados:,} já coletados).")
        confirmacao = input("  Continuar? (s/n): ").strip().lower()
        if confirmacao != "s":
            print("  Cancelado.")
            return
        inicio_loop = pagina_inicio

    erros = []

    for pagina in range(inicio_loop, total_paginas):
        time.sleep(PAUSA_SEG)

        dados = buscar_pagina_com_retry(QUERY, pagina=pagina, tamanho=TAMANHO, filtros=FILTROS)

        if dados is None:
            erros.append({"pagina": pagina, "erro": "Falhou após todos os retries"})
            print(f"  ✗ Página {pagina} falhou definitivamente — continuando...")
            continue

        registros_filtrados = [
            extrair_campos(r) for r in dados.get("registros", [])
            if dentro_do_periodo(r, DATA_INICIO, DATA_FIM)
        ]
        salvar_csv(registros_filtrados, ARQUIVO_CSV, modo="a")
        coletados += len(registros_filtrados)
        pct = (pagina + 1) / total_paginas * 100
        print(f"  Página {pagina:4d}/{total_paginas-1} — {coletados:,} registros ({pct:.1f}%)")

    log = {
        "data_coleta": datetime.now().isoformat(),
        "query": QUERY,
        "filtro_turma": "7ª Turma Cível",
        "filtro_periodo": f"{DATA_INICIO} a {DATA_FIM}",
        "total_esperado_turma": total,
        "total_coletado_periodo": coletados,
        "paginas": total_paginas,
        "tamanho_pagina": TAMANHO,
        "erros": erros,
        "arquivo": ARQUIVO_CSV,
    }
    with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"  Coleta concluída!")
    print(f"  Total coletado (2024-2025) : {coletados:,} acórdãos")
    print(f"  Arquivo CSV               : {ARQUIVO_CSV}")
    print(f"  Log                       : {ARQUIVO_LOG}")
    if erros:
        print(f"  ⚠ {len(erros)} páginas com erro permanente — veja {ARQUIVO_LOG}")
    print("=" * 60)


if __name__ == "__main__":
    main()
