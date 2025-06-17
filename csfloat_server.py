from dotenv import load_dotenv
load_dotenv()  

import os
import sys
import traceback
import httpx
from typing import Any, Dict, List, Union
from mcp.server.fastmcp import FastMCP

# Inicializa o servidor FastMCP
mcp = FastMCP("csfloat")

# Configuração de autenticação
CSFLOAT_API_BASE = "https://csfloat.com/api/v1"
API_KEY = os.getenv("CSFLOAT_API_KEY")
if not API_KEY:
    print("[ERROR] Variável CSFLOAT_API_KEY não definida no ambiente.", file=sys.stderr)
    sys.exit(1)

# Cabeçalhos incluindo autorização de API
HEADERS = {
    "Authorization": API_KEY,
    "Accept": "application/json"
}

async def make_csfloat_request(path: str, params: Dict[str, Any] = None) -> Union[List[Any], None]:
    """Faz requisição autenticada à CSFloat e retorna lista de objetos ou None."""
    url = f"{CSFLOAT_API_BASE}/{path}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=HEADERS, params=params, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            # Retorna lista extraída
            if isinstance(data, dict):
                # API pode envolver em chaves
                if isinstance(data.get("listings"), list):
                    return data["listings"]
                if isinstance(data.get("data"), list):
                    return data["data"]
                return None
            if isinstance(data, list):
                return data
            return None
        except Exception as e:
            code = getattr(e, 'response', None) and getattr(e.response, 'status_code', '')
            print(f"[ERROR] {url} -> {code} {e}", file=sys.stderr)
            if 'resp' in locals():
                print(resp.text, file=sys.stderr)
            return None

@mcp.tool()
async def search_skins(query: str) -> str:
    """Procura skins cujo nome contenha o termo dado, retorna até 10 resultados."""
    listings = await make_csfloat_request("listings", {"limit": 50})
    if not listings:
        return "Não foi possível encontrar skins."
    seen = set()
    results: List[str] = []
    for entry in listings:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item")
        if not isinstance(item, dict):
            continue
        name = item.get("market_hash_name")
        if name and query.lower() in name.lower() and name not in seen:
            seen.add(name)
            results.append(name)
        if len(results) >= 10:
            break
    return "\n".join(results) if results else f"Nenhuma skin encontrada contendo '{query}'"

@mcp.tool()
async def get_skin_float(skin_name: str) -> str:
    """Retorna o menor float ativo para um skin (market_hash_name)."""
    params = {"market_hash_name": skin_name, "limit": 1, "sort_by": "lowest_float"}
    listings = await make_csfloat_request("listings", params)
    # Tenta variação sem '|'
    if not listings:
        alt = skin_name.replace("|", "").strip()
        if alt and alt != skin_name:
            params["market_hash_name"] = alt
            listings = await make_csfloat_request("listings", params)
    if not listings or not isinstance(listings[0], dict):
        return (f"Nenhum float encontrado para '{skin_name}'.\n"
                f"Use 'search_skins' para ver nomes semelhantes.")
    listing = listings[0]
    item = listing.get("item", {}) if isinstance(listing, dict) else {}
    if not isinstance(item, dict):
        return f"Nenhum float disponível para '{skin_name}'."
    fv = item.get("float_value")
    wear = item.get("wear_name", "Unknown")
    return f"Skin: {skin_name}\nMenor float ativo: {fv} ({wear})"

@mcp.tool()
async def get_skin_price(skin_name: str, currency: str = "USD") -> str:
    """Retorna o menor preço ativo para um skin, convertido de cents."""
    params = {"market_hash_name": skin_name, "limit": 1, "sort_by": "lowest_price"}
    listings = await make_csfloat_request("listings", params)
    # Tenta variação sem '|'
    if not listings:
        alt = skin_name.replace("|", "").strip()
        if alt and alt != skin_name:
            params["market_hash_name"] = alt
            listings = await make_csfloat_request("listings", params)
    if not listings or not isinstance(listings[0], dict):
        return (f"Nenhum preço encontrado para '{skin_name}'.\n"
                f"Use 'search_skins' para ver nomes semelhantes.")
    listing = listings[0]
    cents = listing.get("price") if isinstance(listing, dict) else None
    if cents is None:
        return f"Preço não disponível para '{skin_name}'."
    return f"Skin: {skin_name}\nMenor preço ativo: {cents/100:.2f} {currency}"

@mcp.tool()
async def compare_skins(skin1: str, skin2: str) -> str:
    """Compara float e preço entre dois skins."""
    f1 = await get_skin_float(skin1)
    p1 = await get_skin_price(skin1)
    f2 = await get_skin_float(skin2)
    p2 = await get_skin_price(skin2)
    return (
        f"Comparação entre '{skin1}' e '{skin2}':\n\n"
        f"{f1}\n\n{p1}\n\n{f2}\n\n{p2}"
    )

if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
