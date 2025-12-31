import os
import time
import logging
from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, Union

import csv
import uuid
from app.automation.common import definir_turno, capture_failure_screenshot, extrair_tabela_html, converter_csv_para_xlsx, aguardar_download_csv, validar_csv_baixado
from app.automation.actions import fazer_login, fechar_popup
import shutil
from app.utils.browser import get_browser_context, configure_browser_window

#---------------- LOG ----------------
logger = logging.getLogger(__name__)

#---------------- ENV ----------------
load_dotenv()

USERNAME = os.getenv("PORTAL_USER")
PASSWORD = os.getenv("PORTAL_PASS")
URL_REPORT = os.getenv("URL_TEMPO_MEDIO_IFOOD", "")
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "")


def montar_url_rel_tmp_ifood(datahora_inicio: Optional[str] = None, datahora_fim: Optional[str] = None, unidades: Union[list[int], int] = [], horas: Optional[str] = None, ignorar_turno: bool = False) -> str:
    """
    Monta a URL para exportar o relatório TEMPO MÉDIO IFOOD.
    Adicionado parâmetro 'ignorar_turno' para fallback.
    """
    agora = datetime.now()

    def parse_data(valor: str | None, padrao: datetime) -> datetime:
        if not valor:
            return padrao
        try:
            return datetime.strptime(valor, "%d/%m/%Y %H:%M")
        except ValueError:
            logger.warning(f"Formato inválido recebido: {valor}. Utilizando valor padrão")
            return padrao
              
    inicio_mes = parse_data(datahora_inicio, agora.replace(day=1, hour=0, minute=0))
    fim_mes = parse_data(datahora_fim, agora.replace(second=0, microsecond=0))
    
    data_inicio = inicio_mes.strftime("%d/%m/%Y %H:%M")
    data_fim = fim_mes.strftime("%d/%m/%Y %H:%M")

    params = {
        "datahora_inicio": data_inicio,
        "datahora_fim": data_fim,
        "unidades[]": unidades,
        "id_canal": 2
    }

    if not ignorar_turno:
        turno_calculado = definir_turno(horas)
        params["turno"] = turno_calculado

    query = urlencode(params, doseq=True)
    return f"{URL_REPORT}?{query}"

def exportar_rel_tmp_ifood_hibrido(sb, downloads_dir: Path, datahora_inicio: str, datahora_fim: str, unidades: list[int], turno: str, ignorar_turno: bool = False) -> Path:
    """
    Tenta baixar CSV via botão. Usa scraping APENAS como fallback se:
    - Download falhar
    - Arquivo baixado for < 1KB
    """
    downloads_dir.mkdir(parents=True, exist_ok=True)
    
    unique_id = uuid.uuid4().hex[:8]
    
    url = montar_url_rel_tmp_ifood(datahora_inicio, datahora_fim, unidades, turno, ignorar_turno)
    logger.info(f"➡️ Acessando relatório Ifood ({'com turno' if not ignorar_turno else 'sem turno'}): {url}")
    
    sb.open(url)
    sb.wait_for_ready_state_complete(timeout=30)
    
    if sb.is_text_visible("Nenhum registro") or sb.is_text_visible("Sem dados"):
        raise FileNotFoundError("Aviso de 'Sem dados' detectado na tela.")
    
    arquivo_csv_valido = None

    # ========== TENTATIVA 1: DOWNLOAD VIA BOTÃO CSV ==========
    try:
        logger.info("mouse_click Tentando download via botão CSV...")
        btn_csv = "#btn-csv"
        
        if sb.is_element_visible(btn_csv):
            sb.click(btn_csv)
            arquivo_baixado = aguardar_download_csv(downloads_dir, timeout=30)
            
            if arquivo_baixado and validar_csv_baixado(arquivo_baixado, tamanho_minimo=1000):
                logger.info(f"✅ CSV baixado: {arquivo_baixado.stat().st_size} bytes")
                arquivo_csv_valido = arquivo_baixado
            else:
                if arquivo_baixado:
                    logger.warning("⚠️ CSV inválido, será usado scraping")
                    arquivo_baixado.unlink()
                else:
                    logger.warning("⚠️ Download falhou, será usado scraping")
        else:
            logger.warning("⚠️ Botão não encontrado, será usado scraping")
            
    except Exception as e:
        logger.warning(f"⚠️ Erro no download: {e}, será usado scraping")

    # ========== TENTATIVA 2: SCRAPING (APENAS SE DOWNLOAD FALHOU) ==========
    if not arquivo_csv_valido:
        logger.info("🔄 Usando scraping como fallback...")
        file_name = f"ifood_{unique_id}.csv"
        file_path = downloads_dir / file_name

        # Aguarda a tabela aparecer com mais tempo e tentativas
        max_tentativas = 3
        tempo_espera = 5
        
        # Seletores alternativos para tentar encontrar a tabela
        seletores_tabela = ["table", "table.table", "div.table-responsive table", "#conteudo table"]
        tabela_encontrada = False
        
        for tentativa in range(max_tentativas):
            # Tenta cada seletor
            for seletor in seletores_tabela:
                if sb.is_element_visible(seletor):
                    logger.info(f"✅ Tabela detectada na tentativa {tentativa + 1} usando seletor '{seletor}'. Iniciando extração...")
                    tabela_encontrada = True
                    break
            
            if tabela_encontrada:
                break
                
            if tentativa < max_tentativas - 1:
                logger.warning(f"⏳ Tabela não detectada (tentativa {tentativa + 1}/{max_tentativas}). Aguardando {tempo_espera}s...")
                sb.sleep(tempo_espera)
                
                # Verifica se apareceu mensagem de sem dados
                if sb.is_text_visible("Nenhum registro") or sb.is_text_visible("Sem dados"):
                    raise FileNotFoundError("Aviso de 'Sem dados' detectado na tela após espera.")
            else:
                logger.error("❌ Tabela não encontrada após todas as tentativas.")
                raise FileNotFoundError("Tabela não encontrada após espera.")
            
        page_source = sb.get_page_source()
        dados = extrair_tabela_html(page_source)
        
        if not dados:
            raise ValueError("Nenhum dado extraído da tabela.")
            
        logger.info(f"📊 Linhas extraídas: {len(dados)}")
        
        with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerows(dados)
            
        logger.info(f"✅ Arquivo CSV gerado: {file_path}")
        arquivo_csv_valido = file_path
    
    # Converte CSV para XLSX
    xlsx_path = converter_csv_para_xlsx(arquivo_csv_valido)
    arquivo_csv_valido.unlink()
    
    return xlsx_path

def run_automation_and_download(datahora_inicio: Optional[str] = None, datahora_fim: Optional[str] = None, unidades: Union[list[int], int] = 459, turno: Optional[str] = None) -> Path:
    if not USERNAME or not PASSWORD:
        raise ValueError("Credenciais ausentes no .env.")

    start = time.time()
    
    with get_browser_context(headless=True) as sb:
        try:
            sb.driver.set_page_load_timeout(60)
            configure_browser_window(sb)
            downloads_dir = Path(sb.get_downloads_folder())
            
            sb.open(BASE_DOMAIN)
            fazer_login(sb)
            fechar_popup(sb)    
            
            # Preparando Cache (Ponto de montagem persistente em ambiente Docker)
            # Tenta usar /app/downloaded_files se existir, senão usa a pasta temporária
            base_persistente = Path("/app/downloaded_files") if Path("/app/downloaded_files").exists() else downloads_dir
            cache_dir = base_persistente / "cache_tempomedio_ifood"
            cache_dir.mkdir(parents=True, exist_ok=True)
            arquivo_reserva = cache_dir / "tempomedio_ifood_RESERVA.xlsx"

            try:
                arquivo_novo = None

                try:
                    # Tenta exportar com o filtro original
                    arquivo_novo = exportar_rel_tmp_ifood_hibrido(sb, downloads_dir, datahora_inicio, datahora_fim, unidades, turno, ignorar_turno=False)
                
                except FileNotFoundError:
                    # TENTATIVA 2: Sem o turno (Fallback)
                    logger.warning("⚠️ Dados não encontrados com filtro de turno. Tentando SEM turno...")
                    arquivo_novo = exportar_rel_tmp_ifood_hibrido(sb, downloads_dir, datahora_inicio, datahora_fim, unidades, turno, ignorar_turno=True)
                
                # Sucesso: atualiza reserva
                if arquivo_novo:
                    try:
                        if arquivo_reserva.exists():
                            arquivo_reserva.unlink()
                        shutil.copy(str(arquivo_novo), str(arquivo_reserva))
                        logger.info("💾 Reserva de Tempo Médio iFood atualizada.")
                    except Exception as e:
                        logger.warning(f"⚠️ Falha ao atualizar reserva: {e}")
                    
                    logger.info(f"Tempo total da automação: {time.time() - start:.2f}s")
                    return arquivo_novo

            except Exception as e_scrap:
                logger.warning(f"⚠️ Falha no scraping novo: {e_scrap}")
                
                # Falha: usa reserva
                if arquivo_reserva.exists():
                    logger.info("✅ Usando arquivo RESERVA de emergência (Tempo Médio iFood).")
                    nome_emergencia = f"ifood_RESERVA_{uuid.uuid4().hex[:8]}.xlsx"
                    dest = downloads_dir / nome_emergencia
                    shutil.copy(str(arquivo_reserva), str(dest))
                    return dest
                else:
                    raise ValueError(f"Falha no scraping e sem reserva: {e_scrap}")

        except Exception as e:
            msg_erro = str(e)
            # Se for erro de timeout ou elemento não encontrado, tenta tirar print
            d_dir = locals().get('downloads_dir') or Path("erros")
            capture_failure_screenshot(sb, d_dir, "erro_ifood_scraping")
            logger.error(f"Erro fatal na automação Ifood: {e}", exc_info=True)
            
            # Se for aviso de sem dados, propaga FileNotFoundError
            if "Sem dados" in msg_erro or "Nenhum registro" in msg_erro:
                 raise FileNotFoundError(msg_erro)
            raise