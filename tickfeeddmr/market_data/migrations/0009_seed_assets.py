import json
from pathlib import Path

from django.db import migrations

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
BATCH_SIZE = 500


def _read(name):
    with (SEED_DIR / f"{name}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def seed_assets(apps, schema_editor):
    """Заливает справочник активов из снимков `seed/*.json`.

    `ignore_conflicts` — существующие строки (в том числе правленные в админке)
    остаются как есть, повторный прогон ничего не дублирует. Крипто-пары
    создаются неактивными: включаются из админки точечно.
    """
    stock_asset = apps.get_model("market_data", "StockAsset")
    crypto_asset = apps.get_model("market_data", "CryptoAsset")
    fiat_currency = apps.get_model("market_data", "FiatCurrency")

    stock_asset.objects.bulk_create(
        [
            stock_asset(
                symbol=row["symbol"],
                display_name=row["display_name"],
                board="TQBR",
            )
            for row in _read("stocks")
        ],
        batch_size=BATCH_SIZE,
        ignore_conflicts=True,
    )
    crypto_asset.objects.bulk_create(
        [
            crypto_asset(
                symbol=row["symbol"],
                display_name=row["symbol"],
                exchange="BINANCE",
                trading_pair=row["trading_pair"],
                is_active=False,
            )
            for row in _read("crypto")
        ],
        batch_size=BATCH_SIZE,
        ignore_conflicts=True,
    )
    fiat_currency.objects.bulk_create(
        [
            fiat_currency(
                iso_code=row["iso_code"],
                cbr_id=row["cbr_id"],
                symbol=row["iso_code"],
                display_name=row["display_name"],
            )
            for row in _read("fiat")
        ],
        batch_size=BATCH_SIZE,
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("market_data", "0008_alter_fiatcurrency_cbr_id_suffix"),
    ]

    operations = [
        migrations.RunPython(seed_assets, migrations.RunPython.noop),
    ]
