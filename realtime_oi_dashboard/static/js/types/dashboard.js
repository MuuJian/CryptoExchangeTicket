/**
 * @typedef {Object} OiRankingRow
 * @property {string} symbol
 * @property {number | null} price
 * @property {number | null} volume24h
 * @property {number | null} price24hAgo
 * @property {number | null} priceChangePercent
 * @property {number | null} fundingRatePercent
 * @property {number | null} nextFundingTime
 * @property {number | null} currentOi
 * @property {number | null} currentOiValue
 * @property {number | null} changeAmount
 * @property {number | null} changePercent
 * @property {number | null} changeValue
 * @property {number | null} oi24hChangeAmount
 * @property {number | null} oi24hChangePercent
 * @property {number | null} oi24hChangeValue
 * @property {number | null} oi7dChangeAmount
 * @property {number | null} oi7dChangePercent
 * @property {number | null} oi7dChangeValue
 */

/**
 * @typedef {Object} LivePrice
 * @property {number} price
 * @property {number | undefined} volume24h
 */

/**
 * @typedef {Object} TableFilters
 * @property {string} query
 * @property {number} limit
 * @property {number} minOiValue
 * @property {number} minVolume
 * @property {boolean} favoritesOnly
 */

/**
 * @typedef {Object} TableSort
 * @property {string} sortKey
 * @property {"asc" | "desc"} sortDir
 */

export {};
