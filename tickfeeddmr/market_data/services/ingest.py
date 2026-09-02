import logging
from typing import TYPE_CHECKING

from tickfeeddmr.market_data.models import CryptoAsset, CryptoPriceSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.providers.base import TradeEvent

logger = logging.getLogger(__name__)


class CryptoTradeIngestService:
    """Резолвит `CryptoAsset` по `(exchange, trading_pair)` и пишет снапшоты."""

    def __init__(self, *, exchange: str) -> None:
        self._exchange = exchange

    async def write_snapshots(self, events: Sequence[TradeEvent]) -> int:
        """Записать `events` как `CryptoPriceSnapshot`, вернуть число записанных строк.

        `side` не персистится — в этом этапе `CryptoPriceSnapshot` хранит
        только price/volume/timestamp. События с неизвестным
        `trading_pair` (нет активного `CryptoAsset` для `self._exchange`)
        логируются и пропускаются, а не создают актив на лету.
        """
        if not events:
            return 0

        trading_pairs = {event.trading_pair for event in events}
        assets_by_pair = {
            asset.trading_pair: asset
            async for asset in CryptoAsset.objects.filter(
                exchange=self._exchange,
                trading_pair__in=trading_pairs,
            )
        }

        snapshots = []
        for event in events:
            asset = assets_by_pair.get(event.trading_pair)
            if asset is None:
                logger.error(
                    "No CryptoAsset for exchange=%s trading_pair=%s, skipping event",
                    self._exchange,
                    event.trading_pair,
                )
                continue
            snapshots.append(
                CryptoPriceSnapshot(
                    asset=asset,
                    price=event.price,
                    volume=event.volume,
                    timestamp=event.timestamp,
                ),
            )

        await CryptoPriceSnapshot.objects.abulk_create(snapshots)
        return len(snapshots)
