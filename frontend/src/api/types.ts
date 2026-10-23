import type { components } from "@/api/schema";

type Schemas = components["schemas"];


export type Asset = Schemas["AssetOut"];
export type DataFreshness = Schemas["DataFreshness"];

export type CryptoCurrent = Schemas["CryptoCurrentOut"];
export type CryptoTrade = Schemas["CryptoTradeOut"];
export type CryptoTradePage = Schemas["CursorPage_CryptoTradeOut_"];

export type StockAsset = Schemas["StockAssetOut"];
export type StockCurrent = Schemas["StockCurrentOut"];
export type StockTrade = Schemas["StockTradeOut"];
export type StockTradePage = Schemas["CursorPage_StockTradeOut_"];
export type StockPricePoint = Schemas["StockPricePointOut"];

export type Intraday = Schemas["IntradayOut"];
export type PricePoint = Schemas["PricePointOut"];
export type LinearPricePoint = Schemas["LinearPricePointOut"];

export type FiatRate = Schemas["FiatRateOut"];
export type FiatRatePoint = Schemas["FiatRatePointOut"];

export type ErrorModel = Schemas["ErrorModel"];
export type ErrorDetail = Schemas["ErrorDetail"];

type CryptoSSEnvelope =
  Schemas["SSEvent_tickfeeddmr.market_data.api.schemas.crypto.CryptoTradeEventOut___tickfeeddmr.market_data.api.schemas.common.StreamWarningOut___tickfeeddmr.market_data.api.schemas.common.HeartbeatOut_"];
type StockSSEnvelope =
  Schemas["SSEvent_tickfeeddmr.market_data.api.schemas.stock.StockTradeEventOut___tickfeeddmr.market_data.api.schemas.common.StreamWarningOut___tickfeeddmr.market_data.api.schemas.common.HeartbeatOut_"];

export type CryptoStreamEvent = CryptoSSEnvelope["data"];
export type StockStreamEvent = StockSSEnvelope["data"];

export type CryptoTradeEvent = Extract<CryptoStreamEvent, { kind: "trade" }>;
export type StockTradeEvent = Extract<StockStreamEvent, { kind: "trade" }>;
export type StreamWarning = Extract<CryptoStreamEvent, { kind: "warning" }>;
export type Heartbeat = Extract<CryptoStreamEvent, { kind: "heartbeat" }>;

export type AiStatus = Schemas["AiStatusOut"];
export type AiUsage = Schemas["AiUsageOut"];
export type ChatRequest = Schemas["ChatRequestIn"];
export type ChatMessageIn = Schemas["ChatMessageIn"];

type ChatSSEnvelope =
  Schemas["SSEvent_tickfeeddmr.ai.api.schemas.chat.ChatTextDeltaOut___tickfeeddmr.ai.api.schemas.chat.ChatToolCallOut___tickfeeddmr.ai.api.schemas.chat.ChatDoneOut___tickfeeddmr.ai.api.schemas.chat.ChatErrorOut_"];

export type ChatStreamEvent = ChatSSEnvelope["data"];

export type ChatTextDelta = Extract<ChatStreamEvent, { kind: "text_delta" }>;
export type ChatToolCall = Extract<ChatStreamEvent, { kind: "tool_call" }>;
export type ChatDone = Extract<ChatStreamEvent, { kind: "done" }>;
export type ChatError = Extract<ChatStreamEvent, { kind: "error" }>;
