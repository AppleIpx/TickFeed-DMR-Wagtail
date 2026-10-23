from tickfeeddmr.ai.services.tools.errors import ToolInputError
from tickfeeddmr.ai.services.tools.schemas import Market, ResolvedAsset
from tickfeeddmr.market_data.models import CryptoAsset, StockAsset

_MARKET_NAMES = {"crypto": "крипто-активов", "stock": "акций"}


async def resolve_asset(market: Market, symbol: str) -> ResolvedAsset:
    """Активный актив рынка по тикеру; при перепутанном рынке — подсказка."""
    s = symbol.strip()
    model = CryptoAsset if market == "crypto" else StockAsset
    asset = await model.objects.filter(symbol=s, is_active=True).afirst()
    if asset is None:
        found = [
            a async for a in model.objects.filter(symbol__iexact=s, is_active=True)[:2]
        ]
        asset = found[0] if len(found) == 1 else None
    if asset is None:
        other_market: Market = "stock" if market == "crypto" else "crypto"
        other = StockAsset if market == "crypto" else CryptoAsset
        if await other.objects.filter(symbol__iexact=s, is_active=True).aexists():
            msg = f"{s} не найден среди {_MARKET_NAMES[market]}"
            raise ToolInputError(msg, hint=f'{s} доступен как market="{other_market}"')
        msg = f"Актив {s} не найден"
        raise ToolInputError(msg, hint="Список активов — инструмент list_assets")
    return ResolvedAsset(
        market=market,
        symbol=asset.symbol,
        name=asset.display_name,
        asset_id=asset.pk,
        trading_pair=asset.trading_pair if isinstance(asset, CryptoAsset) else None,
    )
