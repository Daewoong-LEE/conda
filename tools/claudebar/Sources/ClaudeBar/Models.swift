import Foundation

// MARK: - Pricing (per 1M tokens, USD)

private let pricing: [String: (inp: Double, out: Double, cw: Double, cr: Double)] = [
    "claude-opus-4-6":            (15.00, 75.00, 18.75, 1.50),
    "claude-sonnet-4-6":          ( 3.00, 15.00,  3.75, 0.30),
    "claude-3-7-sonnet-20250219": ( 3.00, 15.00,  3.75, 0.30),
    "claude-3-5-sonnet-20241022": ( 3.00, 15.00,  3.75, 0.30),
    "claude-3-5-sonnet-20240620": ( 3.00, 15.00,  3.75, 0.30),
    "claude-haiku-4-5":           ( 0.80,  4.00,  1.00, 0.08),
    "claude-haiku-4-5-20251001":  ( 0.80,  4.00,  1.00, 0.08),
    "claude-3-5-haiku-20241022":  ( 0.80,  4.00,  1.00, 0.08),
    "claude-3-opus-20240229":     (15.00, 75.00, 18.75, 1.50),
    "claude-3-sonnet-20240229":   ( 3.00, 15.00,  3.75, 0.30),
    "claude-3-haiku-20240307":    ( 0.25,  1.25,  0.30, 0.03),
]

private let defaultPricing = (inp: 3.00, out: 15.00, cw: 3.75, cr: 0.30)

func lookupPricing(_ model: String) -> (inp: Double, out: Double, cw: Double, cr: Double) {
    if let p = pricing[model] { return p }
    for (key, p) in pricing where model.contains(key) || key.contains(model) { return p }
    return defaultPricing
}

// MARK: - ModelUsage

struct ModelUsage {
    var inputTokens:          Int    = 0
    var outputTokens:         Int    = 0
    var cacheCreationTokens:  Int    = 0
    var cacheReadTokens:      Int    = 0
    var cost:                 Double = 0

    var totalTokens: Int { inputTokens + outputTokens }
}

// MARK: - UsageStats

struct UsageStats {
    var inputTokens:         Int    = 0
    var outputTokens:        Int    = 0
    var cacheCreationTokens: Int    = 0
    var cacheReadTokens:     Int    = 0
    var totalCost:           Double = 0
    var byModel:             [String: ModelUsage] = [:]
    var firstTimestamp:      Date?

    var totalTokens: Int { inputTokens + outputTokens }

    mutating func add(
        model: String,
        inputTokens: Int,
        outputTokens: Int,
        cacheCreationTokens: Int,
        cacheReadTokens: Int,
        timestamp: Date
    ) {
        self.inputTokens         += inputTokens
        self.outputTokens        += outputTokens
        self.cacheCreationTokens += cacheCreationTokens
        self.cacheReadTokens     += cacheReadTokens

        if firstTimestamp == nil || timestamp < firstTimestamp! {
            firstTimestamp = timestamp
        }

        let p = lookupPricing(model)
        let cost = Double(inputTokens)         * p.inp / 1_000_000
                 + Double(outputTokens)        * p.out / 1_000_000
                 + Double(cacheCreationTokens) * p.cw  / 1_000_000
                 + Double(cacheReadTokens)     * p.cr  / 1_000_000
        totalCost += cost

        byModel[model, default: ModelUsage()].inputTokens         += inputTokens
        byModel[model, default: ModelUsage()].outputTokens        += outputTokens
        byModel[model, default: ModelUsage()].cacheCreationTokens += cacheCreationTokens
        byModel[model, default: ModelUsage()].cacheReadTokens     += cacheReadTokens
        byModel[model, default: ModelUsage()].cost                += cost
    }
}

// MARK: - Formatting

func fmtTokens(_ n: Int) -> String {
    switch n {
    case 1_000_000...: return String(format: "%.2fM", Double(n) / 1_000_000)
    case 1_000...:     return String(format: "%.1fk", Double(n) / 1_000)
    default:           return "\(n)"
    }
}

func fmtCost(_ v: Double) -> String {
    v < 0.01 ? String(format: "$%.4f", v) : String(format: "$%.3f", v)
}
