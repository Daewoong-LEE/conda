import Foundation

actor ClaudeAPIService {
    static let shared = ClaudeAPIService()

    private func makeRequest(url: URL, sessionKey: String) -> URLRequest {
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("sessionKey=\(sessionKey)", forHTTPHeaderField: "Cookie")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            forHTTPHeaderField: "User-Agent"
        )
        return req
    }

    func fetchUsage(sessionKey: String) async throws -> (pct: Double, resetMins: Int) {
        // 1. Get org ID
        let orgsReq = makeRequest(url: URL(string: "https://claude.ai/api/organizations")!, sessionKey: sessionKey)
        let (orgsData, _) = try await URLSession.shared.data(for: orgsReq)
        let orgs = try JSONDecoder().decode([Organization].self, from: orgsData)
        guard let orgId = orgs.first?.uuid else { throw URLError(.badServerResponse) }

        // 2. Fetch usage
        let usageReq = makeRequest(
            url: URL(string: "https://claude.ai/api/organizations/\(orgId)/usage")!,
            sessionKey: sessionKey
        )
        let (usageData, _) = try await URLSession.shared.data(for: usageReq)
        let usage = try JSONDecoder().decode(UsageResponse.self, from: usageData)

        guard let five = usage.fiveHour else { throw URLError(.cannotParseResponse) }

        var resetMins = 0
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso.date(from: five.resetsAt) {
            resetMins = max(0, Int(date.timeIntervalSinceNow / 60))
        }

        return (five.utilization, resetMins)
    }
}
