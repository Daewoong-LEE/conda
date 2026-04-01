import Foundation

// MARK: - ClaudeReader

actor ClaudeReader {
    private let projectsDir: URL

    init() {
        projectsDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".claude/projects")
    }

    // Returns aggregated stats for all messages on or after `since`.
    func getStats(since date: Date) async -> UsageStats {
        var stats = UsageStats()
        guard FileManager.default.fileExists(atPath: projectsDir.path) else { return stats }

        let enumerator = FileManager.default.enumerator(
            at: projectsDir,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        )
        while let url = enumerator?.nextObject() as? URL {
            guard url.pathExtension == "jsonl" else { continue }
            parseFile(url, into: &stats, since: date)
        }
        return stats
    }

    // MARK: Private

    private func parseFile(_ url: URL, into stats: inout UsageStats, since cutoff: Date) {
        guard let data = try? Data(contentsOf: url),
              let content = String(data: data, encoding: .utf8) else { return }

        let isoParser = ISO8601DateFormatter()
        isoParser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let isoFallback = ISO8601DateFormatter()   // without fractional seconds

        for line in content.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty,
                  let jsonData = trimmed.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
                  obj["type"] as? String == "assistant"
            else { continue }

            // Timestamp gate
            if let tsStr = obj["timestamp"] as? String {
                let ts = isoParser.date(from: tsStr) ?? isoFallback.date(from: tsStr)
                guard let ts, ts >= cutoff else { continue }
            }

            guard let msg   = obj["message"]  as? [String: Any],
                  let usage = msg["usage"]     as? [String: Any]
            else { continue }

            let model            = msg["model"]                          as? String ?? "unknown"
            let inputTokens      = usage["input_tokens"]                as? Int    ?? 0
            let outputTokens     = usage["output_tokens"]               as? Int    ?? 0
            let cacheCreation    = usage["cache_creation_input_tokens"] as? Int    ?? 0
            let cacheRead        = usage["cache_read_input_tokens"]     as? Int    ?? 0

            guard inputTokens > 0 || outputTokens > 0 else { continue }

            let ts: Date = {
                if let tsStr = obj["timestamp"] as? String {
                    return isoParser.date(from: tsStr) ?? isoFallback.date(from: tsStr) ?? cutoff
                }
                return cutoff
            }()

            stats.add(
                model:               model,
                inputTokens:         inputTokens,
                outputTokens:        outputTokens,
                cacheCreationTokens: cacheCreation,
                cacheReadTokens:     cacheRead,
                timestamp:           ts
            )
        }
    }
}
