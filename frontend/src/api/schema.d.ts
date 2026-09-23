export interface paths {
    "/api/crypto/assets/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCryptoassetlistcontrollerApiCryptoAssets"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/crypto/assets/{symbol}/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCryptoassetcurrentcontrollerApiCryptoAssetsSymbolCurrent"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/crypto/assets/{symbol}/trades": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCryptotradescontrollerApiCryptoAssetsSymbolTrades"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/crypto/assets/{symbol}/intraday": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCryptointradaycontrollerApiCryptoAssetsSymbolIntraday"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/crypto/assets/{symbol}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCryptohistorycontrollerApiCryptoAssetsSymbolHistory"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/crypto/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCryptostreamcontrollerApiCryptoStream"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stocks/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStockassetlistcontrollerApiStocks"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stocks/{secid}/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStockassetcurrentcontrollerApiStocksSecidCurrent"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stocks/{secid}/trades": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStocktradescontrollerApiStocksSecidTrades"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stocks/{secid}/intraday": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStockintradaycontrollerApiStocksSecidIntraday"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stocks/{secid}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStockhistorycontrollerApiStocksSecidHistory"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stocks/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStockstreamcontrollerApiStocksStream"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fiat/rates/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getFiatratelistcontrollerApiFiatRates"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fiat/rates/{iso_code}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getFiathistorycontrollerApiFiatRatesIsoCodeHistory"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AssetOut
         * @description Общий вид торгуемого актива в ответах API — крипта, фиат или акция.
         */
        AssetOut: {
            symbol: string;
            display_name: string;
            is_active: boolean;
        };
        /**
         * CryptoCurrentOut
         * @description Текущая цена крипто-актива.
         */
        CryptoCurrentOut: {
            asset: components["schemas"]["AssetOut"];
            price: string;
            volume: string | null;
            freshness: components["schemas"]["DataFreshness"];
        };
        /**
         * CryptoTradeEventOut
         * @description Событие `trade` SSE-потока крипты: одна сделка, время — с биржи.
         */
        CryptoTradeEventOut: {
            /** @enum {unknown} */
            kind: "trade";
            symbol: string;
            timestamp: string;
            price: string;
            volume: string;
            /** @enum {unknown} */
            side: "buy" | "sell";
            trade_id: string;
            data_delay_seconds: number;
        };
        /**
         * CryptoTradeOut
         * @description Одна сделка из ленты крипто-актива
         */
        CryptoTradeOut: {
            timestamp: string;
            price: string;
            volume: string;
            /** @enum {unknown} */
            side: "buy" | "sell";
            trade_id: string;
        };
        /**
         * CursorPage[CryptoTradeOut]
         * @description Курсорная страница списочного ответа
         */
        CursorPage_CryptoTradeOut_: {
            items: components["schemas"]["CryptoTradeOut"][];
            next_cursor: string | null;
            freshness: components["schemas"]["DataFreshness"];
        };
        /**
         * CursorPage[StockTradeOut]
         * @description Курсорная страница списочного ответа
         */
        CursorPage_StockTradeOut_: {
            items: components["schemas"]["StockTradeOut"][];
            next_cursor: string | null;
            freshness: components["schemas"]["DataFreshness"];
        };
        /**
         * DataFreshness
         * @description Честная метка свежести данных: показывает лаг источника как есть.
         */
        DataFreshness: {
            timestamp: string;
            data_delay_seconds: number;
            is_realtime: boolean;
        };
        /**
         * ErrorDetail
         * @description Base schema for error details description.
         */
        ErrorDetail: {
            loc?: (number | string)[];
            msg: string;
            type?: string;
        };
        /**
         * ErrorModel
         * @description Default error response schema.
         *
         *     Can be customized.
         *     See :ref:`customizing-error-messages` for more details.
         */
        ErrorModel: {
            detail: components["schemas"]["ErrorDetail"][];
        };
        /**
         * FiatRateOut
         * @description Курс валюты ЦБ РФ
         */
        FiatRateOut: {
            asset: components["schemas"]["AssetOut"];
            iso_code: string;
            rate: string;
            /** Format: date */
            effective_date: string;
            /** @enum {unknown} */
            source: "ЦБ РФ";
            freshness: components["schemas"]["DataFreshness"];
        };
        /**
         * FiatRatePointOut
         * @description Точка истории курса валюты.
         */
        FiatRatePointOut: {
            timestamp: string;
            /** Format: date */
            effective_date: string;
            rate: string;
        };
        /**
         * HeartbeatOut
         * @description Служебное событие: поток жив, событий нет.
         *
         *     Встроенный ping DMR выключен (ломает завершение при уходе клиента),
         *     поэтому heartbeat шлёт сам генератор. Для `EventSource` это именованное
         *     событие: слушать через `addEventListener("heartbeat", ...)`.
         */
        HeartbeatOut: {
            /** @enum {unknown} */
            kind: "heartbeat";
            timestamp: string;
        };
        /**
         * IntradayOut
         * @description Ответ `intraday` — точки за скользящие 24 часа + одна свежесть на весь ответ.
         */
        IntradayOut: {
            points: components["schemas"]["LinearPricePointOut"][];
            freshness: components["schemas"]["DataFreshness"];
        };
        /**
         * LinearPricePointOut
         * @description Точка `intraday` — общая линейная схема для крипты и акций.
         */
        LinearPricePointOut: {
            timestamp: string;
            price: string;
            volume: string;
        };
        /**
         * PricePointOut
         * @description Дневная точка истории цены крипто-актива (CryptoDailyCandle).
         *
         *     `close`, не `price`: симметрично `StockPricePointOut`, у которой
         *     OHLC — не экстремумы сессии (как у `intraday`), а настоящая дневная
         *     свеча, то же самое, что и здесь.
         */
        PricePointOut: {
            timestamp: string;
            open: string;
            high: string;
            low: string;
            close: string;
            volume: string;
        };
        /**
         * SSEvent[tickfeeddmr.market_data.api.schemas.crypto.CryptoTradeEventOut | tickfeeddmr.market_data.api.schemas.common.StreamWarningOut | tickfeeddmr.market_data.api.schemas.common.HeartbeatOut]
         * @description Server sent event payload.
         */
        "SSEvent_tickfeeddmr.market_data.api.schemas.crypto.CryptoTradeEventOut___tickfeeddmr.market_data.api.schemas.common.StreamWarningOut___tickfeeddmr.market_data.api.schemas.common.HeartbeatOut_": {
            data: components["schemas"]["CryptoTradeEventOut"] | components["schemas"]["StreamWarningOut"] | components["schemas"]["HeartbeatOut"];
            event?: string | null;
            id?: number | string | null;
            retry?: number | null;
            comment?: string | null;
        };
        /**
         * SSEvent[tickfeeddmr.market_data.api.schemas.stock.StockTradeEventOut | tickfeeddmr.market_data.api.schemas.common.StreamWarningOut | tickfeeddmr.market_data.api.schemas.common.HeartbeatOut]
         * @description Server sent event payload.
         */
        "SSEvent_tickfeeddmr.market_data.api.schemas.stock.StockTradeEventOut___tickfeeddmr.market_data.api.schemas.common.StreamWarningOut___tickfeeddmr.market_data.api.schemas.common.HeartbeatOut_": {
            data: components["schemas"]["StockTradeEventOut"] | components["schemas"]["StreamWarningOut"] | components["schemas"]["HeartbeatOut"];
            event?: string | null;
            id?: number | string | null;
            retry?: number | null;
            comment?: string | null;
        };
        /**
         * StockCurrentOut
         * @description Текущий агрегированный снимок борда по акции
         */
        StockCurrentOut: {
            asset: components["schemas"]["AssetOut"];
            last: string | null;
            open: string | null;
            high: string | null;
            low: string | null;
            change: string | null;
            change_percent: string | null;
            volume: number | null;
            num_trades: number | null;
            freshness: components["schemas"]["DataFreshness"];
        };
        /**
         * StockPricePointOut
         * @description Одна свеча истории цены акции — под свечной график
         */
        StockPricePointOut: {
            timestamp: string;
            open: string | null;
            high: string | null;
            low: string | null;
            close: string | null;
            volume: number | null;
        };
        /**
         * StockTradeEventOut
         * @description Событие `trade` SSE-потока акций: одна сделка, время — от ISS.
         *
         *     `data_delay_seconds` — честная метка лага бесплатной выдачи ISS (~15
         *     минут): `timestamp` — время сделки на бирже, а не момент получения.
         */
        StockTradeEventOut: {
            /** @enum {unknown} */
            kind: "trade";
            secid: string;
            timestamp: string;
            price: string;
            quantity: number;
            /** @enum {unknown} */
            side: "buy" | "sell";
            trade_id: number;
            period: string;
            data_delay_seconds: number;
        };
        /**
         * StockTradeOut
         * @description Одна сделка из ленты акции — только для активов с `track_trades=True`
         */
        StockTradeOut: {
            timestamp: string;
            price: string;
            quantity: number;
            /** @enum {unknown} */
            side: "buy" | "sell";
            trade_id: number;
            period: string;
        };
        /**
         * StreamWarningOut
         * @description Первое событие SSE-потока, если часть тикеров из запроса не найдена.
         *
         *     Поток по остальным тикерам при этом идёт. Если не найден ни один — вместо
         *     потока 404 (см. `StreamAssetsNotFoundError`).
         */
        StreamWarningOut: {
            /** @enum {unknown} */
            kind: "warning";
            unknown: string[];
            detail: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getCryptoassetlistcontrollerApiCryptoAssets: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssetOut"][];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getCryptoassetcurrentcontrollerApiCryptoAssetsSymbolCurrent: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Path-параметр крипто-ручек — символ пары. */
                symbol: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CryptoCurrentOut"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getCryptotradescontrollerApiCryptoAssetsSymbolTrades: {
        parameters: {
            query?: {
                /** @description Query-параметры курсорной пагинации ленты сделок */
                cursor?: string | null;
                /** @description Query-параметры курсорной пагинации ленты сделок */
                limit?: number;
            };
            header?: never;
            path: {
                /** @description Path-параметр крипто-ручек — символ пары. */
                symbol: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CursorPage_CryptoTradeOut_"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getCryptointradaycontrollerApiCryptoAssetsSymbolIntraday: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Path-параметр крипто-ручек — символ пары. */
                symbol: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntradayOut"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getCryptohistorycontrollerApiCryptoAssetsSymbolHistory: {
        parameters: {
            query?: {
                /** @description Query-параметры `history` — период опционален, по умолчанию последний год. */
                from?: string | null;
                /** @description Query-параметры `history` — период опционален, по умолчанию последний год. */
                to?: string | null;
            };
            header?: never;
            path: {
                /** @description Path-параметр крипто-ручек — символ пары. */
                symbol: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PricePointOut"][];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getCryptostreamcontrollerApiCryptoStream: {
        parameters: {
            query?: {
                /**
                 * @description Query SSE-стрима крипты: `symbols=BTC,ETH` — тикеры через запятую.
                 *
                 *     Без параметра поток отдаёт все активные пары.
                 */
                symbols?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    "Cache-Control": string;
                    "X-Accel-Buffering": string;
                    Connection: string;
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["SSEvent_tickfeeddmr.market_data.api.schemas.crypto.CryptoTradeEventOut___tickfeeddmr.market_data.api.schemas.common.StreamWarningOut___tickfeeddmr.market_data.api.schemas.common.HeartbeatOut_"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["ErrorModel"];
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getStockassetlistcontrollerApiStocks: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssetOut"][];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getStockassetcurrentcontrollerApiStocksSecidCurrent: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Path-параметр ручек акций — SECID бумаги. */
                secid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StockCurrentOut"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getStocktradescontrollerApiStocksSecidTrades: {
        parameters: {
            query?: {
                /** @description Query-параметры курсорной пагинации ленты сделок */
                cursor?: string | null;
                /** @description Query-параметры курсорной пагинации ленты сделок */
                limit?: number;
            };
            header?: never;
            path: {
                /** @description Path-параметр ручек акций — SECID бумаги. */
                secid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CursorPage_StockTradeOut_"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getStockintradaycontrollerApiStocksSecidIntraday: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Path-параметр ручек акций — SECID бумаги. */
                secid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntradayOut"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getStockhistorycontrollerApiStocksSecidHistory: {
        parameters: {
            query?: {
                /** @description Query-параметры `history` — период опционален, по умолчанию последний год. */
                from?: string | null;
                /** @description Query-параметры `history` — период опционален, по умолчанию последний год. */
                to?: string | null;
            };
            header?: never;
            path: {
                /** @description Path-параметр ручек акций — SECID бумаги. */
                secid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StockPricePointOut"][];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getStockstreamcontrollerApiStocksStream: {
        parameters: {
            query?: {
                /**
                 * @description Query SSE-стрима акций: `secids=SBER,GAZP` — тикеры через запятую.
                 *
                 *     Без параметра поток отдаёт все активные бумаги с включённой лентой сделок.
                 */
                secids?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    "Cache-Control": string;
                    "X-Accel-Buffering": string;
                    Connection: string;
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["SSEvent_tickfeeddmr.market_data.api.schemas.stock.StockTradeEventOut___tickfeeddmr.market_data.api.schemas.common.StreamWarningOut___tickfeeddmr.market_data.api.schemas.common.HeartbeatOut_"];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["ErrorModel"];
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getFiatratelistcontrollerApiFiatRates: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FiatRateOut"][];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
    getFiathistorycontrollerApiFiatRatesIsoCodeHistory: {
        parameters: {
            query?: {
                /** @description Query-параметры `history` — период опционален, по умолчанию последний год. */
                from?: string | null;
                /** @description Query-параметры `history` — период опционален, по умолчанию последний год. */
                to?: string | null;
            };
            header?: never;
            path: {
                /** @description Path-параметр ручки истории курса валюты — ISO-код. */
                iso_code: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FiatRatePointOut"][];
                };
            };
            /** @description Raised when request components cannot be parsed */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when path parameters do not match */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when provided `Accept` header cannot be satisfied */
            406: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
            /** @description Raised when returned response does not match the response schema */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorModel"];
                };
            };
        };
    };
}
