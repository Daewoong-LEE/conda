import SwiftUI
import Combine

@MainActor
class UsageViewModel: ObservableObject {
    @Published var pct: Double = 0
    @Published var resetMins: Int = 0
    @Published var synced: Bool = false
    @Published var isLoading: Bool = false
    @Published var hasSessionKey: Bool = false

    private var timer: AnyCancellable?
    private let limit = 150_000

    var pctColor: Color {
        pct < 60 ? .green : pct < 85 ? .orange : .red
    }

    var tokensUsed: String {
        let n = Int(Double(limit) * pct / 100)
        if n >= 1_000_000 { return String(format: "%.1fM", Double(n) / 1_000_000) }
        if n >= 1_000     { return String(format: "%.1fk", Double(n) / 1_000) }
        return "\(n)"
    }

    var timeString: String {
        let h = resetMins / 60, m = resetMins % 60
        if h > 0 { return "\(h)h \(m)m" }
        return resetMins > 0 ? "\(resetMins)m" : "—"
    }

    init() {
        hasSessionKey = KeychainService.load() != nil
        if hasSessionKey { Task { await refresh() } }
        timer = Timer.publish(every: 60, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in Task { await self?.refresh() } }
    }

    func refresh() async {
        guard let key = KeychainService.load() else {
            hasSessionKey = false
            return
        }
        isLoading = true
        do {
            let result = try await ClaudeAPIService.shared.fetchUsage(sessionKey: key)
            pct       = result.pct
            resetMins = result.resetMins
            synced    = true
        } catch {
            synced = false
        }
        isLoading = false
    }

    func saveSessionKey(_ key: String) {
        KeychainService.save(key)
        hasSessionKey = true
        Task { await refresh() }
    }

    func signOut() {
        KeychainService.delete()
        hasSessionKey = false
        synced        = false
        pct           = 0
        resetMins     = 0
    }
}
