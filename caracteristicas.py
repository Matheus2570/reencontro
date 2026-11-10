"""Características opcionais e leitura conservadora de cadastros antigos.

Toda extração ocorre em memória; não migra nem altera documentos do Firestore.
"""
import re
from decimal import Decimal

from pesquisa import normalizar


ROTULOS = {
    "marca": "Marca", "modelo": "Modelo", "tipo_objeto": "Tipo do objeto",
    "capacidade": "Capacidade (ml ou L)", "material": "Material",
    "conexao": "Conexão", "formato": "Formato do fone", "rodinhas": "Rodinhas",
    "tamanho": "Tamanho", "identificacao": "Identificação / inscrição",
    "cor": "Cor",
}
CAMPOS_COMUNS = ("marca", "modelo")
CAMPOS_CATEGORIA = {
    "Garrafas e recipientes": ("tipo_objeto", "capacidade", "material"),
    "Roupas e acessórios": ("tipo_objeto", "rodinhas", "tamanho"),
    "Eletrônicos": ("tipo_objeto", "conexao", "formato"),
    "Material escolar": ("tipo_objeto", "material"),
    "Documentos": ("tipo_objeto", "identificacao"),
    "Chaves": ("tipo_objeto", "identificacao"),
    "Outros": ("tipo_objeto", "material"),
}
OPCOES = {
    "conexao": ("", "Bluetooth", "Com fio"),
    "formato": ("", "Intra-auricular", "Sobre a orelha", "Ao redor da orelha"),
    "rodinhas": ("", "Sim", "Não"),
}


def canonico(campo, valor):
    texto = normalizar(str(valor or ""))
    if texto in {"", "nao sei", "nao informado", "desconhecido", "talvez", "nao lembro", "ignorado"} or re.search(
        r"\b(talvez|acho|parece|ou|nao sei)\b", texto
    ):
        return ""
    if campo == "capacidade":
        medida = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(ml|l|litros?|mililitros?)\s*", str(valor).lower())
        if not medida:
            return ""
        digitos = medida[1]
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", digitos):
            digitos = digitos.replace(".", "")
        numero = Decimal(digitos.replace(",", "."))
        if medida[2] in {"l", "litro", "litros"}:
            numero *= 1000
        return f"{numero.normalize():f} ml" if numero > 0 else ""
    aliases = {
        "cor": {
        "preta": "preto", "branca": "branco", "vermelha": "vermelho",
        "amarela": "amarelo", "roxa": "roxo", "prateada": "prata",
        "dourada": "dourado"},
        "material": {"inox": "aco inox", "aco inoxidavel": "aco inox"},
        "conexao": {"sem fio": "bluetooth", "wireless": "bluetooth", "p2": "com fio"},
        "tipo_objeto": {
        "fone de ouvido": "fone", "fones de ouvido": "fone", "fones": "fone",
        },
    }
    texto = aliases.get(campo, {}).get(texto, texto)
    if campo == "cor":
        if re.search(r"\b(nao|sem)\b", texto):
            return ""
        cores = {aliases["cor"].get(c, c) for c in texto.split()
                 if c in {"azul", "verde", "preto", "preta", "branco", "branca", "vermelho", "vermelha",
                          "amarelo", "amarela", "roxo", "roxa", "rosa", "laranja", "marrom", "cinza",
                          "bege", "prata", "prateada", "dourado", "dourada", "transparente", "incolor"}}
        return cores.pop() if len(cores) == 1 else ""
    return texto


def extrair_capacidade(texto):
    """Limita negações e incertezas à oração que contém a medida.

    Pontuação e conjunções separam observações; vírgulas/pontos decimais
    permanecem na medida. Uma medida negada ou mais de um valor não autoriza
    inferir capacidade, mesmo que outra oração contenha um valor afirmativo.
    """
    oracoes = re.split(
        r"[;!?\n]|(?<!\d)[.,]|[.,](?!\d)|\b(?:e|mas|porém|porem)\b",
        texto.lower(),
    )
    valores = set()
    for oracao in oracoes:
        medidas = re.findall(
            r"(?<![-\w.,])\d+(?:[.,]\d+)?\s*(?:ml|l|litros?|mililitros?)\b", oracao
        )
        if not medidas:
            continue
        if re.search(r"\b(talvez|acho|parece|nao|sem|ou|aproximadamente|cerca)\b", normalizar(oracao)):
            return ""
        for medida in medidas:
            valor = canonico("capacidade", medida)
            if not valor:
                return ""
            valores.add(valor)
    return valores.pop() if len(valores) == 1 else ""


def extrair_caracteristicas(item):
    """Só assume valores explícitos, únicos e sem linguagem de incerteza."""
    campos = CAMPOS_COMUNS + CAMPOS_CATEGORIA.get(item.get("categoria"), ()) + ("cor",)
    valores = {}
    estruturados = item.get("caracteristicas") or {}
    if not isinstance(estruturados, dict):
        estruturados = {}
    texto = normalizar(f"{item.get('nome', '')}. {item.get('descricao', '')}")
    incerto = bool(re.search(r"\b(talvez|acho|parece|nao|ou)\b", texto))
    # Marca/modelo desconhecidos continuam utilizáveis quando rotulados explicitamente.
    original = f"{item.get('nome', '')}; {item.get('descricao', '')}"
    for campo in campos:
        bruto = item.get("cor", "") if campo == "cor" else estruturados.get(campo, "")
        valor = canonico(campo, bruto)
        if valor:
            valores[campo] = valor
            continue
        if campo == "capacidade":
            capacidade = extrair_capacidade(original)
            if capacidade:
                valores[campo] = capacidade
            continue
        if incerto or campo == "cor":
            continue
        achados = []
        if campo in {"marca", "modelo"}:
            achados = re.findall(rf"\b{campo}\s*:\s*([^;,.\n]+)", original, re.I)
        if campo == "marca" and not achados:
            marcas = r"(stanley|camelbak|contigo|tupperware|jbl|sony|samsung|apple|nike|adidas|jansport|kipling|dell|lenovo)"
            achados = re.findall(
                rf"\b(?:garrafa|copo|mochila|fone|fones|fone de ouvido|fones de ouvido|estojo|notebook|marca)\s+{marcas}\b", texto
            )
        if campo == "tipo_objeto":
            achados = re.findall(r"\b(garrafa|copo|mochila|estojo|fone|fones|casaco|chave|carteira)\b", texto)
        if campo == "conexao":
            achados = re.findall(r"\b(bluetooth|sem fio|com fio|p2)\b", texto)
        if campo == "material":
            achados = re.findall(r"\b(?:material|garrafa de|copo de|mochila de|estojo de)\s+(aco inoxidavel|aco inox|inox|plastico|vidro|aluminio)\b", texto)
        if campo == "rodinhas":
            achados = ["Não"] if "sem rodinhas" in texto else (["Sim"] if "com rodinhas" in texto else [])
        unicos = {canonico(campo, achado) for achado in achados} - {""}
        if len(unicos) == 1:
            valores[campo] = unicos.pop()
    return valores


def comparar_caracteristicas(origem, candidato):
    a, b = extrair_caracteristicas(origem), extrair_caracteristicas(candidato)
    campos = dict.fromkeys(CAMPOS_COMUNS + CAMPOS_CATEGORIA.get(origem.get("categoria"), ()) + ("cor",))
    detalhes = []
    for campo in campos:
        estado = "Não informado" if campo not in a or campo not in b else (
            "Compatível" if a[campo] == b[campo] else "Divergente"
        )
        detalhes.append({"Característica": ROTULOS[campo], "Origem": a.get(campo, "Não informado"),
                         "Candidato": b.get(campo, "Não informado"), "Resultado": estado})
    divergencias = [d for d in detalhes if d["Resultado"] == "Divergente"]
    compativeis = sum(d["Resultado"] == "Compatível" for d in detalhes)
    return {"detalhes": detalhes, "divergencias": divergencias, "compativeis": compativeis,
            "situacao": "Com divergências" if divergencias else (
                "Compatível nos dados informados" if compativeis else "Dados insuficientes")}
