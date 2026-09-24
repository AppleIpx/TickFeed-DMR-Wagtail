from django.conf import settings

from tickfeeddmr.market_data.services.stream_settings import validate_positive


def validate_crypto_asset_change_settings() -> None:
    """Все `MARKET_DATA_CRYPTO_ASSET_CHANGES_*` числовые настройки положительные."""
    validate_positive(
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_MAXLEN",
        settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_MAXLEN,
    )
    validate_positive(
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_BLOCK_MS",
        settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_BLOCK_MS,
    )
    validate_positive(
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_COUNT",
        settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_COUNT,
    )
    validate_positive(
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_PUBLISH_TIMEOUT_SECONDS",
        settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_PUBLISH_TIMEOUT_SECONDS,
    )
